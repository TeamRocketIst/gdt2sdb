from pathlib import Path

from gdt2r2sdb.sanitizer import clean_name_for_sdb, sanitize_header_text, discover_struct_names

FIX = Path(__file__).parent / "fixtures" / "mini_il2cpp.h"


def test_clean_name_preserves_double_and_leading_underscores():
    assert clean_name_for_sdb("Mono_ValueTuple_T1__T2__Fields") == "Mono_ValueTuple_T1__T2__Fields"
    assert clean_name_for_sdb("__9__17_0") == "__9__17_0"
    assert clean_name_for_sdb("___c") == "___c"


def test_sanitizer_rewrites_msvc_ints_and_injects_forward_typedefs():
    text = FIX.read_text()
    out = sanitize_header_text(text)
    assert "unsigned __int64" not in out
    assert "unsigned long long" in out
    assert "typedef struct MethodInfo MethodInfo;" in out
    assert "typedef struct Il2CppClass Il2CppClass;" in out


def test_discover_struct_names_realistic_subset():
    names = discover_struct_names(FIX.read_text())
    assert "MethodInfo" in names
    assert "UnityEngine_MonoBehaviour_Fields" in names
