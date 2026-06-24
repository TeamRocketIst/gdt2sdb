from collections import OrderedDict
from pathlib import Path

from gdt2r2sdb.subset import read_sdb_text, subset_records, write_sdb_text


def write_demo_sdb(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "bool=type",
                "type.bool=b",
                "type.bool.size=8",
                "int32_t=type",
                "type.int32_t=d",
                "type.int32_t.size=32",
                "intptr_t=type",
                "type.intptr_t=q",
                "type.intptr_t.size=64",
                "float=type",
                "type.float=f",
                "type.float.size=32",
                "void=type",
                "type.void=v",
                "type.void.size=0",
                "DemoObject_Fields=struct",
                "struct.DemoObject_Fields=m_CachedPtr",
                "struct.DemoObject_Fields.m_CachedPtr=intptr_t,0,0",
                "DemoComponent_Fields=struct",
                "struct.DemoComponent_Fields=super",
                "struct.DemoComponent_Fields.super=DemoObject_Fields,0,0",
                "DemoBehaviour_Fields=struct",
                "struct.DemoBehaviour_Fields=super",
                "struct.DemoBehaviour_Fields.super=DemoComponent_Fields,0,0",
                "DemoMonoBehaviour_Fields=struct",
                "struct.DemoMonoBehaviour_Fields=super,cancelSource",
                "struct.DemoMonoBehaviour_Fields.super=DemoBehaviour_Fields,0,0",
                "struct.DemoMonoBehaviour_Fields.cancelSource=void *,8,0",
                "DemoColor_o=struct",
                "struct.DemoColor_o=fields",
                "struct.DemoColor_o.fields=DemoColor_Fields,0,0",
                "DemoColor_Fields=struct",
                "struct.DemoColor_Fields=r,g,b,a",
                "struct.DemoColor_Fields.r=float,0,0",
                "struct.DemoColor_Fields.g=float,4,0",
                "struct.DemoColor_Fields.b=float,8,0",
                "struct.DemoColor_Fields.a=float,12,0",
                "DemoVector3_o=struct",
                "struct.DemoVector3_o=fields",
                "struct.DemoVector3_o.fields=DemoVector3_Fields,0,0",
                "DemoVector3_Fields=struct",
                "struct.DemoVector3_Fields=x,y,z",
                "struct.DemoVector3_Fields.x=float,0,0",
                "struct.DemoVector3_Fields.y=float,4,0",
                "struct.DemoVector3_Fields.z=float,8,0",
                "DemoController_c=struct",
                "DemoString_o=struct",
                "DemoWidget_o=struct",
                "DemoController_o=struct",
                "struct.DemoController_o=klass,monitor,fields",
                "struct.DemoController_o.klass=DemoController_c *,0,0",
                "struct.DemoController_o.monitor=void *,8,0",
                "struct.DemoController_o.fields=DemoController_Fields,16,0",
                "DemoController_Fields=struct",
                "struct.DemoController_Fields=super,title,seconds,enabled,tint,scale,widget",
                "struct.DemoController_Fields.super=DemoMonoBehaviour_Fields,0,0",
                "struct.DemoController_Fields.title=DemoString_o *,16,0",
                "struct.DemoController_Fields.seconds=int32_t,24,0",
                "struct.DemoController_Fields.enabled=bool,28,0",
                "struct.DemoController_Fields.tint=DemoColor_Fields,32,0",
                "struct.DemoController_Fields.scale=DemoVector3_Fields,48,0",
                "struct.DemoController_Fields.widget=DemoWidget_o *,64,0",
                "PrivateGameName_Fields=struct",
                "struct.PrivateGameName_Fields=secret",
                "struct.PrivateGameName_Fields.secret=int32_t,0,0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_subset_keeps_root_and_by_value_dependencies_without_private_fixture_names(tmp_path):
    src = tmp_path / "all.sdbtxt"
    out = tmp_path / "subset.sdbtxt"
    write_demo_sdb(src)
    records = read_sdb_text(src)

    keys = subset_records(records, ["DemoController_o"])
    write_sdb_text(out, records, keys)
    text = out.read_text()

    assert "DemoController_o=struct\n" in text
    assert "struct.DemoController_o.fields=DemoController_Fields,16,0\n" in text
    assert "struct.DemoController_Fields.tint=DemoColor_Fields,32,0\n" in text
    assert "struct.DemoController_Fields.scale=DemoVector3_Fields,48,0\n" in text
    assert "struct.DemoColor_Fields=r,g,b,a\n" in text
    assert "struct.DemoVector3_Fields=x,y,z\n" in text
    assert "struct.DemoObject_Fields.m_CachedPtr=intptr_t,0,0\n" in text
    assert "type.bool=b\n" in text
    assert "type.int32_t=d\n" in text
    assert "type.intptr_t=q\n" in text

    # Pointer targets are kept shallow by default, which is enough for r2 to print them as p.
    assert "DemoString_o=struct\n" in text
    assert "DemoWidget_o=struct\n" in text

    # Unrelated/private-looking records must not be copied.
    assert "PrivateGameName" not in text


def test_subset_can_follow_pointer_target_layouts(tmp_path):
    src = tmp_path / "all.sdbtxt"
    write_demo_sdb(src)
    records = read_sdb_text(src)

    records["struct.DemoWidget_o"] = "fields"
    records["struct.DemoWidget_o.fields"] = "DemoWidget_Fields,0,0"
    records["DemoWidget_Fields"] = "struct"
    records["struct.DemoWidget_Fields"] = "value"
    records["struct.DemoWidget_Fields.value"] = "int32_t,0,0"

    keys = subset_records(records, ["DemoController_o"], follow_pointers=True)
    assert "DemoWidget_Fields" in keys
    assert "struct.DemoWidget_Fields.value" in keys
