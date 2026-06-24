from pathlib import Path

from gdt2r2sdb.verify import parse_sdb_text, parse_struct_fields, strip_comments

ROOT = Path(__file__).parent / "fixtures"
JAVA_EXPORTER = Path(__file__).resolve().parents[1] / "src" / "gdt2r2sdb" / "ghidra_scripts" / "GdtToR2SdbText.java"


def test_initializer_fixture_has_by_value_il2cpp_value_type_wrappers():
    structs, _ = parse_struct_fields(strip_comments((ROOT / "mini_il2cpp.h").read_text()))
    assert structs["UnityEngine_Color_o"] == ["fields"]
    assert structs["UnityEngine_Vector3_o"] == ["fields"]
    assert structs["initializer_o"] == ["klass", "monitor", "fields"]
    assert structs["initializer_Fields"] == ["super", "styleDeepBlue", "buttonStartScale"]


def test_good_sdb_keeps_top_level_value_type_wrappers_but_unboxes_embedded_fields():
    good_sdb = """
UnityEngine_Color_Fields=struct
struct.UnityEngine_Color_Fields=r,g,b,a
UnityEngine_Color_o=struct
struct.UnityEngine_Color_o=fields
struct.UnityEngine_Color_o.fields=UnityEngine_Color_Fields,0,0
UnityEngine_Vector3_Fields=struct
struct.UnityEngine_Vector3_Fields=x,y,z
UnityEngine_Vector3_o=struct
struct.UnityEngine_Vector3_o=fields
struct.UnityEngine_Vector3_o.fields=UnityEngine_Vector3_Fields,0,0
initializer_Fields=struct
struct.initializer_Fields=super,styleDeepBlue,buttonStartScale
struct.initializer_Fields.super=UnityEngine_MonoBehaviour_Fields,0,0
struct.initializer_Fields.styleDeepBlue=UnityEngine_Color_Fields,16,0
struct.initializer_Fields.buttonStartScale=UnityEngine_Vector3_Fields,32,0
"""
    structs, _, kv = parse_sdb_text(good_sdb)

    # Top-level *_o structs are still exported, so `tk UnityEngine_Color_o`
    # and direct casts still work.
    assert structs["UnityEngine_Color_o"] == ["fields"]
    assert kv["struct.UnityEngine_Color_o.fields"] == "UnityEngine_Color_Fields,0,0"
    assert structs["UnityEngine_Vector3_o"] == ["fields"]
    assert kv["struct.UnityEngine_Vector3_o.fields"] == "UnityEngine_Vector3_Fields,0,0"

    # But when such value-type wrappers are embedded inside a larger struct,
    # the field record uses the inner *_Fields type. This avoids r2 `ts`
    # returning blank for large structs such as initializer_o.
    assert structs["initializer_Fields"] == ["super", "styleDeepBlue", "buttonStartScale"]
    assert kv["struct.initializer_Fields.styleDeepBlue"].startswith("UnityEngine_Color_Fields,")
    assert kv["struct.initializer_Fields.buttonStartScale"].startswith("UnityEngine_Vector3_Fields,")


def test_java_exporter_has_r2_field_type_unboxing_for_value_type_wrappers():
    java = JAVA_EXPORTER.read_text()
    assert "r2FieldType" in java
    assert "valueTypeObjectFields" in java
    assert "name.endsWith(\"_o\")" in java
    assert 'fieldName.equals("fields")' in java
    assert '+ "_Fields"' in java
    assert "r2Type(fieldType)" in java
