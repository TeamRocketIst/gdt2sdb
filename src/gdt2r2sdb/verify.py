from __future__ import annotations

import argparse
import re
from pathlib import Path


def strip_comments(s: str) -> str:
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    s = re.sub(r"//.*", "", s)
    return s


def match_brace(s: str, open_i: int) -> int:
    depth = 0
    i = open_i
    n = len(s)
    while i < n:
        c = s[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        elif c in ('"', "'"):
            q = c
            i += 1
            while i < n:
                if s[i] == "\\":
                    i += 2
                    continue
                if s[i] == q:
                    break
                i += 1
        i += 1
    return -1


def find_defs(s: str):
    pat = re.compile(r"\b(struct|union)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{")
    out = []
    i = 0
    while True:
        m = pat.search(s, i)
        if not m:
            break
        open_i = s.find("{", m.start())
        close_i = match_brace(s, open_i)
        if close_i < 0:
            break
        semi = s.find(";", close_i)
        if semi < 0:
            break
        out.append((m.group(1), m.group(2), m.start(), open_i + 1, close_i, semi))
        i = semi + 1
    return out


def split_decls(body: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = par = br = 0
    for i, c in enumerate(body):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c == "(":
            par += 1
        elif c == ")":
            par -= 1
        elif c == "[":
            br += 1
        elif c == "]":
            br -= 1
        elif c == ";" and depth == 0 and par == 0 and br == 0:
            item = body[start:i].strip()
            if item:
                parts.append(item)
            start = i + 1
    return parts


def parse_field_decl(stmt: str) -> list[str]:
    stmt = stmt.strip()
    if not stmt:
        return []
    # Anonymous union/struct. If there is no field name, flatten its members for comparison with Ghidra's components.
    m = re.match(r"^(struct|union)\s*\{(.*)\}\s*([A-Za-z_][A-Za-z0-9_]*)?(?:\s*\[[^\]]+\])?\s*$", stmt, flags=re.S)
    if m:
        inner = m.group(2)
        opt_name = m.group(3)
        if opt_name:
            return [opt_name]
        names: list[str] = []
        for sub in split_decls(inner):
            names.extend(parse_field_decl(sub))
        return names
    # Named nested definition with field name: struct Foo { ... } name;
    m = re.match(r"^(struct|union)\s+[A-Za-z_][A-Za-z0-9_]*\s*\{.*\}\s*([A-Za-z_][A-Za-z0-9_]*)?(?:\s*\[[^\]]+\])?\s*$", stmt, flags=re.S)
    if m:
        return [m.group(2)] if m.group(2) else []
    # Function pointer field: ret (*name)(args)
    m = re.search(r"\(\s*\*\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*\(", stmt)
    if m:
        return [m.group(1)]
    stmt = stmt.split("=", 1)[0].strip()
    decls: list[str] = []
    depth = 0
    start = 0
    for i, c in enumerate(stmt):
        if c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
        elif c == "," and depth == 0:
            decls.append(stmt[start:i].strip())
            start = i + 1
    decls.append(stmt[start:].strip())
    names: list[str] = []
    for d in decls:
        d = re.sub(r"\[[^\]]*\]\s*$", "", d).strip()
        ms = list(re.finditer(r"[A-Za-z_][A-Za-z0-9_]*", d))
        if ms:
            names.append(ms[-1].group(0))
    return names


def parse_struct_fields(text: str) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    defs = find_defs(text)
    structs: dict[str, list[str]] = {}
    unions: dict[str, list[str]] = {}
    for kind, name, _, bs, be, _ in defs:
        body = text[bs:be]
        fields: list[str] = []
        for stmt in split_decls(body):
            fields.extend(parse_field_decl(stmt))
        (structs if kind == "struct" else unions)[name] = fields
    return structs, unions


def parse_sdb_text(text: str) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, str]]:
    kv: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        kv[k] = v
    structs: dict[str, list[str]] = {}
    unions: dict[str, list[str]] = {}
    for name, kind in list(kv.items()):
        if kind == "struct":
            structs[name] = [x for x in kv.get("struct." + name, "").split(",") if x]
        elif kind == "union":
            unions[name] = [x for x in kv.get("union." + name, "").split(",") if x]
    return structs, unions, kv


def verify(header: Path, sdbtxt: Path | None = None, samples: list[str] | None = None) -> int:
    text = strip_comments(header.read_text(errors="replace"))
    h_structs, h_unions = parse_struct_fields(text)
    print(f"HEADER structs={len(h_structs)} unions={len(h_unions)} struct_fields={sum(map(len, h_structs.values()))} union_fields={sum(map(len, h_unions.values()))}")
    for name in samples or []:
        if name in h_structs:
            print(f"HEADER struct {name}: {len(h_structs[name])} fields: {','.join(h_structs[name])}")
        elif name in h_unions:
            print(f"HEADER union {name}: {len(h_unions[name])} fields: {','.join(h_unions[name])}")
    if not sdbtxt:
        return 0
    st = sdbtxt.read_text(errors="replace")
    s_structs, s_unions, kv = parse_sdb_text(st)
    missing_structs = sorted(set(h_structs) - set(s_structs))
    missing_unions = sorted(set(h_unions) - set(s_unions))
    bad = []
    for name, fields in h_structs.items():
        got = s_structs.get(name)
        if got is not None and got != fields:
            bad.append((name, fields, got))
    print(f"SDB structs={len(s_structs)} unions={len(s_unions)}")
    print(f"MISSING_STRUCTS={len(missing_structs)}")
    print(f"MISSING_UNIONS={len(missing_unions)}")
    print(f"FIELD_MISMATCHES={len(bad)}")
    for name, exp, got in bad[:20]:
        print(f"MISMATCH {name}: expected={exp} got={got}")
    if missing_structs[:20]:
        print("MISSING_STRUCTS sample:", ",".join(missing_structs[:20]))
    if missing_unions[:20]:
        print("MISSING_UNIONS sample:", ",".join(missing_unions[:20]))
    return 1 if missing_structs or missing_unions or bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compare header struct fields against gdt2r2sdb SDB text")
    ap.add_argument("header")
    ap.add_argument("--sdbtxt")
    ap.add_argument("--sample", action="append", default=["VirtualInvokeData", "Il2CppClass", "MethodInfo", "UnityEngine_MonoBehaviour_Fields"])
    ns = ap.parse_args(argv)
    return verify(Path(ns.header), Path(ns.sdbtxt) if ns.sdbtxt else None, ns.sample)


if __name__ == "__main__":
    raise SystemExit(main())
