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
    # Keep loader output deterministic while the script runs.  The footer
    # restores the user-visible settings that we temporarily disable here.
    fp.write("e scr.color=false\n")
    fp.write("e scr.utf8=false\n")
    fp.write("e bin.cache=true\n")
    if not quiet:
        fp.write("?e loading r2 type keys from generated gdt2sdb loader\n")


def _write_footer(fp: TextIO, *, quiet: bool, restore_settings: bool) -> None:
    if not quiet:
        fp.write("?e done loading gdt2sdb r2 type loader\n")
    if restore_settings:
        # r2 scripts do not have a portable way to snapshot arbitrary eval
        # variables before changing them, so restore the interactive-friendly
        # values most users expect after loading.
        fp.write("e scr.color=auto\n")
        fp.write("e scr.utf8=true\n")


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
    restore_settings: bool = True,
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
        _write_footer(fp, quiet=True, restore_settings=restore_settings)
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
    ap.add_argument(
        "--no-restore-settings",
        action="store_true",
        help="do not append commands that restore scr.color and scr.utf8 after loading",
    )
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
        restore_settings=not ns.no_restore_settings,
    )
    if not ns.quiet:
        kind = "compressed r2 loader" if ns.gzip else "r2 loader"
        print(f"[+] wrote {kind}: {out_path}")
        print(f"[+] records: {count}")
        if ns.gzip:
            print(f"[+] gzip is intended for storage/transport; decompress to a real .r2 file before loading")
        else:
            print(f"[+] load in r2: . {out_path}")
            print(f"[+] command line: r2 -q -i {out_path} ./binary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
