from pathlib import Path

from gdt2r2sdb.core import arch_language, copy_ghidra_scripts

ROOT = Path(__file__).resolve().parents[1]
JAVA_DIR = ROOT / "src" / "gdt2r2sdb" / "ghidra_scripts"


def test_arm64_language():
    lang, compiler, dummy = arch_language("arm64", 64, "little")
    assert lang == "AARCH64:LE:64:v8A"
    assert compiler == "default"
    assert dummy == b"\xc0\x03\x5f\xd6"


def test_java_scripts_are_real_files_not_python_strings():
    header = JAVA_DIR / "HeaderToGdt.java"
    exporter = JAVA_DIR / "GdtToR2SdbText.java"
    assert header.is_file()
    assert exporter.is_file()
    assert "public class HeaderToGdt extends GhidraScript" in header.read_text()
    assert "public class GdtToR2SdbText extends GhidraScript" in exporter.read_text()

    # Regression: the Python package should not contain embedded Java templates anymore.
    pkg_text = "\n".join(p.read_text(errors="replace") for p in (ROOT / "src" / "gdt2r2sdb").glob("*.py"))
    assert "HEADER_TO_GDT_JAVA" not in pkg_text
    assert "GDT_TO_R2_SDB_JAVA" not in pkg_text


def test_java_exporter_keeps_conservative_names():
    text = (JAVA_DIR / "GdtToR2SdbText.java").read_text()
    assert '"ptr_' not in text
    assert "return cleanName(n);" in text
    assert 'replaceAll("_+"' not in text


def test_java_exporter_handles_actual_header_regressions():
    text = (JAVA_DIR / "GdtToR2SdbText.java").read_text()
    assert "isAnonymousAggregateComponent" in text
    assert "isSyntheticComponentName" in text
    assert "field7_0x38" in text
    assert "appendComponent" in text
    assert "UnityEngine_UIElements_UnsignedIntegerField_UxmlFactory_Fields" in text
    assert "do not classify user structures" in text
    assert "Cannot resolve type 'type.Il2CppMethodPointer'" in text
    assert 'kv("type." + name, "p")' in text
    assert "valueTypeObjectFields" in text
    assert "r2Type(fieldType)" in text


def test_copy_ghidra_scripts(tmp_path):
    copy_ghidra_scripts(tmp_path)
    assert (tmp_path / "HeaderToGdt.java").is_file()
    assert (tmp_path / "GdtToR2SdbText.java").is_file()


def test_pyproject_exposes_subset_cli():
    text = (ROOT / "pyproject.toml").read_text()
    assert 'gdt2sdb-subset = "gdt2r2sdb.subset:main"' in text


def test_pyproject_exposes_r2loader_cli():
    text = (ROOT / "pyproject.toml").read_text()
    assert 'gdt2sdb-r2loader = "gdt2r2sdb.loader:main"' in text
