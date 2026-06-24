import os
import shutil
import subprocess
from pathlib import Path

import pytest

from gdt2r2sdb.core import ConvertOptions, convert
from gdt2r2sdb.verify import parse_sdb_text

ROOT = Path(__file__).parent / "fixtures"


@pytest.mark.skipif(not os.environ.get("GHIDRA_HEADLESS"), reason="GHIDRA_HEADLESS not set")
def test_ghidra_minimal_header_roundtrip(tmp_path):
    out_gdt = tmp_path / "mini.gdt"
    out_sdbtxt = tmp_path / "mini.sdb.txt"
    timings = convert(ConvertOptions(
        header=str(ROOT / "mini_il2cpp.h"),
        out_gdt=str(out_gdt),
        out_sdbtxt=str(out_sdbtxt),
        ghidra=os.environ["GHIDRA_HEADLESS"],
        arch="arm64",
        bits=64,
        quiet=True,
    ))
    assert out_gdt.exists()
    assert out_sdbtxt.exists()
    structs, unions, kv = parse_sdb_text(out_sdbtxt.read_text())
    assert structs["Il2CppClass"] == ["_1", "static_fields", "rgctx_data", "_2", "vtable"]
    assert structs["UnityEngine_MonoBehaviour_Fields"] == ["super", "m_CancellationTokenSource"]
    assert structs["Mono_ValueTuple_T1__T2__Fields"] == ["Item1", "Item2"]
    assert structs["MethodInfo"] == ["methodPointer", "invoker_method", "name", "klass", "rgctx_data", "methodMetadataHandle", "token"]
    assert "UnityEngine_UIElements_UnsignedIntegerField_UxmlFactory_Fields" in structs
    assert "UnityEngine_UIElements_UxmlUnsignedIntAttributeDescription___c_Fields" in structs
    assert "_gdt2r2" not in "\n".join(structs.keys())


@pytest.mark.skipif(not (os.environ.get("GHIDRA_HEADLESS") and shutil.which("sdb") and shutil.which("r2")), reason="need GHIDRA_HEADLESS, sdb and r2")
def test_radare2_loads_minimal_sdb(tmp_path):
    out_gdt = tmp_path / "mini.gdt"
    out_sdbtxt = tmp_path / "mini.sdb.txt"
    out_sdb = tmp_path / "mini.sdb"
    convert(ConvertOptions(
        header=str(ROOT / "mini_il2cpp.h"),
        out_gdt=str(out_gdt),
        out_sdbtxt=str(out_sdbtxt),
        out_sdb=str(out_sdb),
        ghidra=os.environ["GHIDRA_HEADLESS"],
        arch="arm64",
        bits=64,
        quiet=True,
    ))
    dummy = tmp_path / "dummy.bin"
    dummy.write_bytes(b"\xc0\x03\x5f\xd6")
    cmd = ["r2", "-q0", "-e", "scr.color=0", "-c", f"tos {out_sdb}", "-c", "ts", "-c", "q", str(dummy)]
    out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
    assert "Il2CppClass" in out
    assert "UnityEngine_MonoBehaviour_Fields" in out
