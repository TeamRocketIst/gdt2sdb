from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import __version__
from .core import ConvertOptions, convert


def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Ghidra headless C/GDT to radare2 type SDB converter")
    ap.add_argument("--version", action="version", version=f"gdt2r2sdb {__version__}")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--header", help="input C header; use '-' to read pasted header from stdin")
    src.add_argument("--gdt", help="existing input .gdt archive; skips header parsing")

    ap.add_argument("--out-gdt", help="output/intermediate .gdt path")
    ap.add_argument("--out-sdbtxt", help="optional output radare2 type SDB text path; useful for verification")
    ap.add_argument("--out-sdb", help="compiled SDB output path, load with r2 'tos <file>'")
    ap.add_argument("--ghidra", help="path to Ghidra support/analyzeHeadless")
    ap.add_argument("--sdb", default=shutil.which("sdb") or "sdb", help="path to radare2 sdb command")
    ap.add_argument("--bits", type=int, choices=(32, 64), default=64, help="pointer size")
    ap.add_argument("--arch", default="x86", help="x86, x64, arm64/aarch64, arm")
    ap.add_argument("--endian", choices=("little", "big", "le", "be"), default="little")
    ap.add_argument("--language", default=None, help="override Ghidra language id")
    ap.add_argument("--compiler", default=None, help="override Ghidra compiler spec id")
    ap.add_argument("--include", action="append", default=[], help="include path for C parser; can be repeated")
    ap.add_argument("--cpp-arg", action="append", default=[], help="extra C parser/preprocessor arg; can be repeated")
    ap.add_argument("--sanitize-header", action="store_true", default=True, help="normalize MSVC-ish int types and add parser prelude; default on")
    ap.add_argument("--no-sanitize-header", action="store_false", dest="sanitize_header")
    ap.add_argument("--parser-log", action="store_true", help="print Ghidra C parser messages; off by default for speed")
    ap.add_argument("--default-cc", default="", help="default function calling convention to write into func.*.cc")
    ap.add_argument("--workdir", help="keep generated Java scripts and sanitized header in this directory")
    ap.add_argument("--keep-ghidra-project", action="store_true", help="do not delete temporary Ghidra project")
    ap.add_argument("--quiet", action="store_true")
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_argparser()
    ns = ap.parse_args(argv)
    opts = ConvertOptions(**vars(ns))
    timings = convert(opts)
    if not ns.quiet:
        print("[+] done")
        for key in ("sanitize_header", "ghidra_header_to_gdt", "ghidra_gdt_to_sdbtxt", "compile_sdb", "total"):
            if key in timings:
                print(f"    {key}: {float(timings[key]):.3f}s")
        if "sdbtxt" in timings and ns.out_sdbtxt:
            print(f"[+] wrote SDB text: {timings['sdbtxt']}")
        if "sdb" in timings:
            print(f"[+] wrote SDB: {timings['sdb']}")
            print(f"[+] load in r2: tos {timings['sdb']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
