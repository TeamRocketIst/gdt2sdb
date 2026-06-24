from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from .sanitizer import sanitize_header_text


@dataclass
class ConvertOptions:
    header: str | None = None
    gdt: str | None = None
    out_gdt: str | None = None
    out_sdbtxt: str | None = None
    out_sdb: str | None = None
    ghidra: str | None = None
    sdb: str = "sdb"
    bits: int = 64
    arch: str = "x86"
    endian: str = "little"
    language: str | None = None
    compiler: str | None = None
    include: list[str] = field(default_factory=list)
    cpp_arg: list[str] = field(default_factory=list)
    sanitize_header: bool = True
    parser_log: bool = False
    default_cc: str = ""
    workdir: str | None = None
    keep_ghidra_project: bool = False
    quiet: bool = False


def resolve_headless(user_value: str | None) -> str:
    candidates: list[Path] = []
    if user_value:
        candidates.append(Path(user_value).expanduser())
    if os.environ.get("GHIDRA_HEADLESS"):
        candidates.append(Path(os.environ["GHIDRA_HEADLESS"]).expanduser())
    if os.environ.get("GHIDRA_HOME"):
        candidates.append(Path(os.environ["GHIDRA_HOME"]).expanduser() / "support" / "analyzeHeadless")
    if shutil.which("analyzeHeadless"):
        candidates.append(Path(shutil.which("analyzeHeadless") or ""))

    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    raise SystemExit("Could not find analyzeHeadless. Use --ghidra or set GHIDRA_HEADLESS/GHIDRA_HOME.")


def arch_language(arch: str, bits: int, endian: str) -> tuple[str, str, bytes]:
    a = arch.lower().replace("_", "-")
    le = endian.lower() in ("little", "le")
    if a in ("arm64", "aarch64", "armv8"):
        return "AARCH64:%s:%d:v8A" % ("LE" if le else "BE", bits), "default", (b"\xc0\x03\x5f\xd6" if le else b"\xd6\x5f\x03\xc0")
    if a in ("arm", "arm32"):
        return "ARM:%s:32:v8" % ("LE" if le else "BE"), "default", (b"\x1e\xff\x2f\xe1" if le else b"\xe1\x2f\xff\x1e")
    if a in ("x86", "i386", "x86-32"):
        return "x86:LE:32:default", "gcc", b"\xc3"
    if a in ("x64", "x86-64", "amd64", "x86_64"):
        return "x86:LE:64:default", "gcc", b"\xc3"
    return ("x86:LE:64:default" if bits == 64 else "x86:LE:32:default"), "gcc", b"\xc3"


def copy_ghidra_scripts(script_dir: Path) -> None:
    script_dir.mkdir(parents=True, exist_ok=True)
    for name in ("HeaderToGdt.java", "GdtToR2SdbText.java"):
        data = resources.files("gdt2r2sdb.ghidra_scripts").joinpath(name).read_text(encoding="utf-8")
        (script_dir / name).write_text(data, encoding="utf-8")


def run(cmd: list[str], *, input_bytes: bytes | None = None, verbose: bool = True) -> str:
    if verbose:
        print("+", " ".join(map(str, cmd)), flush=True)
    proc = subprocess.run(
        cmd,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = proc.stdout.decode("utf-8", errors="replace") if proc.stdout else ""
    if verbose and output:
        print(output, end="" if output.endswith("\n") else "\n")

    fatal_markers = (
        "REPORT SCRIPT ERROR",
        "GhidraScriptLoadException",
        "ClassNotFoundException",
        "Failed to get OSGi bundle containing script",
        "Failed to load text sdb",
        "SCRIPT ERROR",
    )
    if proc.returncode != 0 or any(marker in output for marker in fatal_markers):
        raise SystemExit(f"command failed with exit code {proc.returncode}: {' '.join(cmd)}\n{output}")
    return output


def run_ghidra_script(
    headless: str,
    script_dir: Path,
    script_name: str,
    script_args: list[str],
    language: str,
    dummy_bytes: bytes,
    keep_project: bool,
    verbose: bool,
) -> None:
    with tempfile.TemporaryDirectory(prefix="gdt2r2-ghidra-proj-") as td:
        project_dir = Path(td)
        dummy = project_dir / "dummy.bin"
        dummy.write_bytes(dummy_bytes)
        cmd = [
            headless,
            str(project_dir),
            "gdt2r2_tmp",
            "-import", str(dummy),
            "-processor", language,
            "-noanalysis",
            "-scriptPath", str(script_dir),
            "-postScript", script_name,
        ] + script_args
        if not keep_project:
            cmd.append("-deleteProject")
        run(cmd, verbose=verbose)


def compile_sdb_text(sdb_exe: str, in_txt: Path, out_sdb: Path, verbose: bool) -> None:
    sdb_path = shutil.which(sdb_exe) or sdb_exe
    if not shutil.which(sdb_path) and not Path(sdb_path).is_file():
        raise SystemExit("sdb command not found; install radare2/sdb or omit --out-sdb and compile later")
    if not in_txt.is_file() or in_txt.stat().st_size == 0:
        raise SystemExit(f"SDB text was not produced or is empty: {in_txt}")

    out_sdb.parent.mkdir(parents=True, exist_ok=True)
    if out_sdb.exists():
        out_sdb.unlink()

    try:
        run([sdb_path, str(out_sdb), "==", str(in_txt)], verbose=verbose)
    except SystemExit:
        run([sdb_path, str(out_sdb), "="], input_bytes=in_txt.read_bytes(), verbose=verbose)

    if not out_sdb.is_file() or out_sdb.stat().st_size == 0:
        raise SystemExit(f"compiled SDB was not produced or is empty: {out_sdb}")


def convert(opts: ConvertOptions) -> dict[str, float | str]:
    if bool(opts.header) == bool(opts.gdt):
        raise SystemExit("Exactly one of --header or --gdt is required")
    if opts.bits not in (32, 64):
        raise SystemExit("--bits must be 32 or 64")

    verbose = not opts.quiet
    headless = resolve_headless(opts.ghidra)
    lang_default, compiler_default, dummy_bytes = arch_language(opts.arch, opts.bits, opts.endian)
    language = opts.language or lang_default
    compiler = opts.compiler or compiler_default

    temp_ctx: tempfile.TemporaryDirectory[str] | None = None
    if opts.workdir:
        work = Path(opts.workdir).expanduser().resolve()
        work.mkdir(parents=True, exist_ok=True)
    else:
        temp_ctx = tempfile.TemporaryDirectory(prefix="gdt2r2-work-")
        work = Path(temp_ctx.name).resolve()

    timings: dict[str, float | str] = {}
    total_start = time.perf_counter()
    try:
        script_dir = work / "ghidra_scripts"
        copy_ghidra_scripts(script_dir)

        if opts.gdt:
            gdt_path = Path(opts.gdt).expanduser().resolve()
            if not gdt_path.is_file():
                raise SystemExit(f"GDT file not found: {gdt_path}")
        else:
            if not opts.out_gdt:
                raise SystemExit("--out-gdt is required when --header is used")
            gdt_path = Path(opts.out_gdt).expanduser().resolve()
            if opts.header == "-":
                input_header = work / "pasted_input.h"
                input_header.write_text(sys.stdin.read(), encoding="utf-8")
            else:
                input_header = Path(str(opts.header)).expanduser().resolve()
                if not input_header.is_file():
                    raise SystemExit(f"header file not found: {input_header}")

            t0 = time.perf_counter()
            if opts.sanitize_header:
                header_for_ghidra = work / ("__gdt2r2_sanitized__" + input_header.name)
                header_for_ghidra.write_text(
                    sanitize_header_text(input_header.read_text(encoding="utf-8", errors="replace")),
                    encoding="utf-8",
                )
            else:
                header_for_ghidra = input_header
            timings["sanitize_header"] = time.perf_counter() - t0

            include_paths = [str(Path(p).expanduser().resolve()) for p in opts.include]
            include_arg = os.pathsep.join(include_paths) if include_paths else "-"
            t0 = time.perf_counter()
            run_ghidra_script(
                headless,
                script_dir,
                "HeaderToGdt.java",
                [str(header_for_ghidra), str(gdt_path), language, compiler, str(bool(opts.parser_log)).lower(), include_arg] + list(opts.cpp_arg),
                language,
                dummy_bytes,
                opts.keep_ghidra_project,
                verbose,
            )
            timings["ghidra_header_to_gdt"] = time.perf_counter() - t0
            if not gdt_path.is_file() or gdt_path.stat().st_size == 0:
                raise SystemExit(f"Ghidra did not produce a non-empty GDT: {gdt_path}")

        if opts.out_sdbtxt:
            out_sdbtxt = Path(opts.out_sdbtxt).expanduser().resolve()
            keep_sdbtxt = True
        elif opts.out_sdb:
            out_sdbtxt = work / "__gdt2r2_types.sdb.txt"
            keep_sdbtxt = False
        else:
            raise SystemExit("--out-sdb or --out-sdbtxt is required")

        t0 = time.perf_counter()
        run_ghidra_script(
            headless,
            script_dir,
            "GdtToR2SdbText.java",
            [str(gdt_path), str(out_sdbtxt), str(opts.bits), opts.default_cc],
            language,
            dummy_bytes,
            opts.keep_ghidra_project,
            verbose,
        )
        timings["ghidra_gdt_to_sdbtxt"] = time.perf_counter() - t0
        if not out_sdbtxt.is_file() or out_sdbtxt.stat().st_size == 0:
            raise SystemExit(f"Ghidra did not produce a non-empty SDB text file: {out_sdbtxt}")
        timings["sdbtxt"] = str(out_sdbtxt)

        if opts.out_sdb:
            out_sdb = Path(opts.out_sdb).expanduser().resolve()
            t0 = time.perf_counter()
            compile_sdb_text(opts.sdb, out_sdbtxt, out_sdb, verbose)
            timings["compile_sdb"] = time.perf_counter() - t0
            timings["sdb"] = str(out_sdb)
            if not keep_sdbtxt:
                try:
                    out_sdbtxt.unlink()
                except OSError:
                    pass

        timings["total"] = time.perf_counter() - total_start
        return timings
    finally:
        if temp_ctx is not None:
            temp_ctx.cleanup()
