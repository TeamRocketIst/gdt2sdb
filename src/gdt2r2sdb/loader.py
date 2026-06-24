from __future__ import annotations

import argparse
import gzip
from pathlib import Path
from typing import TextIO

from .subset import read_sdb_text


PRIMITIVE_FIXUPS = [
    ("type.bool", "b"),
    ("type.bool.size", "8"),
    ("type.int8_t", "b"),
    ("type.int8_t.size", "8"),
    ("type.uint8_t", "b"),
    ("type.uint8_t.size", "8"),
    ("type.int16_t", "w"),
    ("type.int16_t.size", "16"),
    ("type.uint16_t", "w"),
    ("type.uint16_t.size", "16"),
    ("type.int32_t", "d"),
    ("type.int32_t.size", "32"),
    ("type.uint32_t", "d"),
    ("type.uint32_t.size", "32"),
    ("type.int64_t", "q"),
    ("type.int64_t.size", "64"),
    ("type.uint64_t", "q"),
    ("type.uint64_t.size", "64"),
    ("type.intptr_t", "q"),
    ("type.intptr_t.size", "64"),
    ("type.uintptr_t", "q"),
    ("type.uintptr_t.size", "64"),
    ("type.size_t", "q"),
    ("type.size_t.size", "64"),
    ("type.float", "f"),
    ("type.float.size", "32"),
    ("type.double", "F"),
    ("type.double.size", "64"),
]


class R2LoaderError(SystemExit):
    pass


def _write_header(fp: TextIO, *, quiet: bool) -> None:
    fp.write("e scr.color=false\n")
    fp.write("e scr.utf8=false\n")
    fp.write("e bin.cache=true\n")
    if not quiet:
        fp.write("?e loading r2 type keys from generated gdt2sdb loader\n")


def _write_primitive_fixups(fp: TextIO, *, quiet: bool) -> None:
    if not quiet:
        fp.write("?e reprime primitive type records\n")
    for key, value in PRIMITIVE_FIXUPS:
        fp.write(f"tk {key}={value}\n")


def write_r2_loader(
    sdbtxt: Path,
    out: Path,
    *,
    gzip_output: bool = False,
    progress_interval: int = 50_000,
    primitive_fixups: bool = True,
    quiet: bool = False,
) -> int:
    """Write an r2 script containing `tk key=value` commands for every SDB text record."""
    records = read_sdb_text(sdbtxt)
    out.parent.mkdir(parents=True, exist_ok=True)

    opener = gzip.open if gzip_output else open
    mode = "wt"
    kwargs = {"encoding": "utf-8", "newline": "\n"}
    if gzip_output:
        # gzip.open accepts encoding/newline in text mode.
        kwargs["compresslevel"] = 9

    with opener(out, mode, **kwargs) as fp:  # type: ignore[arg-type]
        _write_header(fp, quiet=quiet)
        for idx, (key, value) in enumerate(records.items(), start=1):
            fp.write(f"tk {key}={value}\n")
            if progress_interval > 0 and idx % progress_interval == 0 and not quiet:
                fp.write(f"?e loaded {idx} type keys\n")
        if primitive_fixups:
            _write_primitive_fixups(fp, quiet=quiet)
        if not quiet:
            fp.write(f"?e done loading {len(records)} type keys\n")
    return len(records)


def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=(
            "Generate a radare2 script that loads gdt2sdb SDB text records with `tk key=value` commands. "
            "This bypasses r2 `tos` for very large type databases."
        )
    )
    ap.add_argument("--sdbtxt", required=True, help="input radare2 SDB text produced by gdt2sdb")
    ap.add_argument("--out-r2", required=True, help="output r2 loader script; use .r2.gz with --gzip for compressed output")
    ap.add_argument("--gzip", action="store_true", help="write gzip-compressed r2 script")
    ap.add_argument(
        "--progress-interval",
        type=int,
        default=50_000,
        help="emit an r2 progress message every N records; use 0 to disable",
    )
    ap.add_argument(
        "--no-primitive-fixups",
        action="store_true",
        help="do not append primitive type re-prime commands such as `tk type.int32_t=d`",
    )
    ap.add_argument("--quiet", action="store_true", help="do not include progress/status messages in the generated script")
    return ap


def main(argv: list[str] | None = None) -> int:
    ns = build_argparser().parse_args(argv)
    in_path = Path(ns.sdbtxt).expanduser().resolve()
    out_path = Path(ns.out_r2).expanduser().resolve()
    count = write_r2_loader(
        in_path,
        out_path,
        gzip_output=bool(ns.gzip),
        progress_interval=max(0, int(ns.progress_interval)),
        primitive_fixups=not ns.no_primitive_fixups,
        quiet=bool(ns.quiet),
    )
    if not ns.quiet:
        kind = "compressed r2 loader" if ns.gzip else "r2 loader"
        print(f"[+] wrote {kind}: {out_path}")
        print(f"[+] records: {count}")
        if ns.gzip:
            print(f"[+] bash/zsh: r2 -q -i <(gzip -dc {out_path}) ./binary")
        else:
            print(f"[+] load in r2: . {out_path}")
            print(f"[+] command line: r2 -q -i {out_path} ./binary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
