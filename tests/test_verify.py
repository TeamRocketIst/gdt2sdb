from pathlib import Path

from gdt2r2sdb.verify import parse_struct_fields, parse_sdb_text, strip_comments

ROOT = Path(__file__).parent / "fixtures"


def test_header_parser_preserves_super_and_anonymous_union_fields():
    structs, unions = parse_struct_fields(strip_comments((ROOT / "mini_il2cpp.h").read_text()))
    assert structs["UnityEngine_Component_Fields"] == ["super"]
    assert structs["UnityEngine_MonoBehaviour_Fields"] == ["super", "m_CancellationTokenSource"]
    assert structs["MethodInfo"] == [
        "methodPointer",
        "invoker_method",
        "name",
        "klass",
        "rgctx_data",
        "methodMetadataHandle",
        "token",
    ]
    assert structs["Mono_ValueTuple_T1__T2__Fields"] == ["Item1", "Item2"]
    assert structs["UnityEngine_UIElements_UnsignedIntegerField_UxmlFactory_Fields"] == ["super"]
    assert structs["UnityEngine_UIElements_UxmlUnsignedIntAttributeDescription___c_Fields"] == []


def test_sdb_parser_sees_structs_and_fields():
    structs, unions, kv = parse_sdb_text((ROOT / "mini_expected.sdb.txt").read_text())
    assert "Il2CppClass" in structs
    assert structs["Il2CppClass"] == ["_1", "static_fields", "rgctx_data", "_2", "vtable"]
    assert structs["UnityEngine_Component_Fields"] == ["super"]
    assert kv["struct.UnityEngine_MonoBehaviour_Fields.super"] == "UnityEngine_Behaviour_Fields,0,0"
    assert "Mono_ValueTuple_T1__T2__Fields" in structs
    assert "UnityEngine_UIElements_UnsignedIntegerField_UxmlFactory_Fields" in structs
    assert "UnityEngine_UIElements_UxmlUnsignedIntAttributeDescription___c_Fields" in structs
