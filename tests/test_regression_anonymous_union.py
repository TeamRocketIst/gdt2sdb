from pathlib import Path

from gdt2r2sdb.verify import parse_sdb_text, parse_struct_fields, strip_comments

ROOT = Path(__file__).parent / "fixtures"
JAVA_EXPORTER = Path(__file__).resolve().parents[1] / "src" / "gdt2r2sdb" / "ghidra_scripts" / "GdtToR2SdbText.java"


def test_methodinfo_anonymous_union_expected_fields_from_header():
    structs, _ = parse_struct_fields(strip_comments((ROOT / "mini_il2cpp.h").read_text()))
    assert structs["MethodInfo"] == [
        "methodPointer",
        "invoker_method",
        "name",
        "klass",
        "rgctx_data",
        "methodMetadataHandle",
        "token",
    ]


def test_verifier_detects_bad_ghidra_synthetic_field_names():
    bad_sdb = """
MethodInfo=struct
struct.MethodInfo=methodPointer,invoker_method,name,klass,field7_0x20,token
struct.MethodInfo.methodPointer=Il2CppMethodPointer,0,0
struct.MethodInfo.invoker_method=InvokerMethod,8,0
struct.MethodInfo.name=char *,16,0
struct.MethodInfo.klass=Il2CppClass *,24,0
struct.MethodInfo.field7_0x20=anon_union_1,32,0
struct.MethodInfo.token=uint32_t,40,0
"""
    structs, _, _ = parse_sdb_text(bad_sdb)
    assert structs["MethodInfo"] != [
        "methodPointer",
        "invoker_method",
        "name",
        "klass",
        "rgctx_data",
        "methodMetadataHandle",
        "token",
    ]
    assert "field7_0x20" in structs["MethodInfo"]


def test_good_sdb_flattens_methodinfo_anonymous_union_members():
    structs, _, _ = parse_sdb_text((ROOT / "mini_expected.sdb.txt").read_text())
    assert structs["MethodInfo"] == [
        "methodPointer",
        "invoker_method",
        "name",
        "klass",
        "rgctx_data",
        "methodMetadataHandle",
        "token",
    ]
    assert not any(name.startswith("field") for name in structs["MethodInfo"])


def test_java_exporter_treats_ghidra_fieldN_offsets_as_anonymous_components():
    java = JAVA_EXPORTER.read_text()
    assert "isSyntheticComponentName" in java
    assert "field7_0x38" in java
    assert "rgctx_data, methodMetadataHandle, genericMethod, genericContainerHandle" in java
    assert 'matches("field\\\\d+(_0x[0-9a-f]+)?")' in java


def test_function_pointer_typedefs_have_type_records_for_r2_ts():
    _, _, kv = parse_sdb_text((ROOT / "mini_expected.sdb.txt").read_text())

    # Regression for r2 `ts MethodInfo` warnings like:
    #   Cannot resolve type 'type.Il2CppMethodPointer' assuming pointer
    #   Cannot resolve type 'type.InvokerMethod' assuming pointer
    assert kv["type.Il2CppMethodPointer"] == "p"
    assert kv["type.Il2CppMethodPointer.size"] == "64"
    assert kv["type.InvokerMethod"] == "p"
    assert kv["type.InvokerMethod.size"] == "64"


def test_java_exporter_emits_function_pointer_typedef_type_records():
    java = JAVA_EXPORTER.read_text()
    assert "Cannot resolve type 'type.Il2CppMethodPointer'" in java
    assert 'kv("type." + name, "p")' in java
    assert 'kv("type." + name + ".size", Integer.toString(pointerBits))' in java
