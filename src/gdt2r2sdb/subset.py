from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from collections import OrderedDict
from pathlib import Path


PRIMITIVE_NAMES = {
    "void",
    "bool",
    "char",
    "int8_t",
    "uint8_t",
    "int16_t",
    "uint16_t",
    "int32_t",
    "uint32_t",
    "int64_t",
    "uint64_t",
    "intptr_t",
    "uintptr_t",
    "size_t",
    "float",
    "double",
}

QUALIFIERS = {
    "const",
    "volatile",
    "struct",
    "union",
    "enum",
    "signed",
    "unsigned",
}


class SdbSubsetError(SystemExit):
    pass


def read_sdb_text(path: Path) -> OrderedDict[str, str]:
    records: OrderedDict[str, str] = OrderedDict()
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        records[key] = value
    return records


def write_sdb_text(path: Path, records: OrderedDict[str, str], keys: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fp:
        for key in keys:
            if key in records:
                fp.write(f"{key}={records[key]}\n")


def _add_key(out: OrderedDict[str, None], records: OrderedDict[str, str], key: str) -> None:
    if key in records and key not in out:
        out[key] = None


def _add_prefix(out: OrderedDict[str, None], records: OrderedDict[str, str], prefix: str) -> None:
    for key in records:
        if key.startswith(prefix):
            _add_key(out, records, key)


def strip_type_name(type_name: str) -> tuple[str, bool]:
    """Return (base_name, is_pointer_like) for an r2 SDB field type."""
    t = type_name.strip()
    is_pointer = "*" in t
    t = t.replace("*", " ")
    t = re.sub(r"\[[^\]]*\]", " ", t)
    tokens = [tok for tok in re.split(r"\s+", t.strip()) if tok]
    tokens = [tok for tok in tokens if tok not in QUALIFIERS]
    if not tokens:
        return "", is_pointer
    return tokens[-1], is_pointer


def field_value_type(value: str) -> tuple[str, bool]:
    # struct.Foo.bar=Type,offset,array_count
    raw_type = value.split(",", 1)[0].strip()
    return strip_type_name(raw_type)


def is_struct_or_union(records: OrderedDict[str, str], name: str) -> bool:
    return records.get(name) in {"struct", "union"}


def is_primitive_or_known_type(records: OrderedDict[str, str], name: str) -> bool:
    return name in PRIMITIVE_NAMES or records.get(name) == "type" or f"type.{name}" in records


def include_primitive_records(out: OrderedDict[str, None], records: OrderedDict[str, str]) -> None:
    for name in sorted(PRIMITIVE_NAMES):
        _add_key(out, records, name)
        _add_key(out, records, f"type.{name}")
        _add_key(out, records, f"type.{name}.size")
        pointer_name = f"{name} *"
        _add_key(out, records, pointer_name)
        _add_key(out, records, f"type.{pointer_name}")
        _add_key(out, records, f"type.{pointer_name}.size")


def include_shallow_type(out: OrderedDict[str, None], records: OrderedDict[str, str], name: str) -> None:
    if not name:
        return
    _add_key(out, records, name)
    _add_key(out, records, f"type.{name}")
    _add_key(out, records, f"type.{name}.size")
    _add_key(out, records, f"typedef.{name}")
    _add_prefix(out, records, f"typedef.{name}.")
    _add_prefix(out, records, f"func.{name}")

    pointer_name = f"{name} *"
    _add_key(out, records, pointer_name)
    _add_key(out, records, f"type.{pointer_name}")
    _add_key(out, records, f"type.{pointer_name}.size")


def include_full_type(
    out: OrderedDict[str, None],
    records: OrderedDict[str, str],
    name: str,
    *,
    follow_pointers: bool,
    seen: set[str],
) -> None:
    if not name or name in seen:
        return
    seen.add(name)

    include_shallow_type(out, records, name)

    kind = records.get(name)
    if kind == "struct":
        _add_key(out, records, f"struct.{name}")
        # Include individual field records and recurse into by-value dependencies.
        prefix = f"struct.{name}."
        for key, value in records.items():
            if not key.startswith(prefix):
                continue
            _add_key(out, records, key)
            if key.endswith(".meta"):
                continue
            dep, pointer_like = field_value_type(value)
            if not dep:
                continue
            if pointer_like and not follow_pointers:
                include_shallow_type(out, records, dep)
            elif not is_primitive_or_known_type(records, dep) or is_struct_or_union(records, dep):
                include_full_type(out, records, dep, follow_pointers=follow_pointers, seen=seen)
            else:
                include_shallow_type(out, records, dep)
    elif kind == "union":
        _add_key(out, records, f"union.{name}")
        prefix = f"union.{name}."
        for key, value in records.items():
            if not key.startswith(prefix):
                continue
            _add_key(out, records, key)
            if key.endswith(".meta"):
                continue
            dep, pointer_like = field_value_type(value)
            if not dep:
                continue
            if pointer_like and not follow_pointers:
                include_shallow_type(out, records, dep)
            elif not is_primitive_or_known_type(records, dep) or is_struct_or_union(records, dep):
                include_full_type(out, records, dep, follow_pointers=follow_pointers, seen=seen)
            else:
                include_shallow_type(out, records, dep)


def subset_records(
    records: OrderedDict[str, str],
    roots: list[str],
    *,
    follow_pointers: bool = False,
    include_primitives: bool = True,
) -> list[str]:
    out: OrderedDict[str, None] = OrderedDict()
    if include_primitives:
        include_primitive_records(out, records)
    seen: set[str] = set()
    for root in roots:
        include_full_type(out, records, root, follow_pointers=follow_pointers, seen=seen)
    return list(out.keys())


def compile_sdb_text(sdb_exe: str, in_txt: Path, out_sdb: Path, *, verbose: bool = True) -> None:
    sdb_path = shutil.which(sdb_exe) or sdb_exe
    if not shutil.which(sdb_path) and not Path(sdb_path).is_file():
        raise SdbSubsetError(f"sdb/r2sdb command not found: {sdb_exe}")
    if out_sdb.exists():
        out_sdb.unlink()
    cmd = [sdb_path, str(out_sdb), "==", str(in_txt)]
    if verbose:
        print("+", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = proc.stdout.decode("utf-8", errors="replace") if proc.stdout else ""
    if verbose and output:
        print(output, end="" if output.endswith("\n") else "\n")
    if proc.returncode != 0:
        raise SdbSubsetError(f"command failed: {' '.join(cmd)}\n{output}")


def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Extract a small radare2 type SDB subset for one or more root types. Useful when r2 chokes on very large IL2CPP type databases."
    )
    ap.add_argument("--sdbtxt", required=True, help="input radare2 SDB text produced by gdt2sdb")
    ap.add_argument("--root", action="append", required=True, help="root type to keep; can be repeated, e.g. initializer_o")
    ap.add_argument("--out-sdbtxt", required=True, help="output subset SDB text")
    ap.add_argument("--out-sdb", help="optional compiled subset .sdb")
    ap.add_argument("--sdb", default=shutil.which("r2sdb") or shutil.which("sdb") or "r2sdb", help="r2sdb/sdb command used when --out-sdb is set")
    ap.add_argument("--follow-pointers", action="store_true", help="recursively include pointer target layouts too; default keeps pointer targets shallow")
    ap.add_argument("--no-primitives", action="store_true", help="do not automatically include primitive type records")
    ap.add_argument("--quiet", action="store_true")
    return ap


def main(argv: list[str] | None = None) -> int:
    ns = build_argparser().parse_args(argv)
    in_path = Path(ns.sdbtxt).expanduser().resolve()
    out_txt = Path(ns.out_sdbtxt).expanduser().resolve()
    records = read_sdb_text(in_path)
    keys = subset_records(
        records,
        ns.root,
        follow_pointers=bool(ns.follow_pointers),
        include_primitives=not ns.no_primitives,
    )
    write_sdb_text(out_txt, records, keys)
    if not ns.quiet:
        print(f"[+] wrote subset SDB text: {out_txt}")
        print(f"[+] records: {len(keys)}")
        missing_roots = [root for root in ns.root if root not in records]
        if missing_roots:
            print(f"[!] missing root records: {', '.join(missing_roots)}")
    if ns.out_sdb:
        out_sdb = Path(ns.out_sdb).expanduser().resolve()
        compile_sdb_text(ns.sdb, out_txt, out_sdb, verbose=not ns.quiet)
        if not ns.quiet:
            print(f"[+] wrote subset SDB: {out_sdb}")
            print(f"[+] load in r2: tos {out_sdb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
