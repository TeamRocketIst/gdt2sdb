import gzip
from pathlib import Path

from gdt2r2sdb.loader import write_r2_loader


def write_demo(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "bool=type",
                "type.bool=b",
                "type.bool.size=8",
                "int32_t=type",
                "type.int32_t=d",
                "type.int32_t.size=32",
                "Demo_o=struct",
                "struct.Demo_o=klass,fields",
                "struct.Demo_o.klass=Demo_c *,0,0",
                "struct.Demo_o.fields=Demo_Fields,16,0",
                "Demo_Fields=struct",
                "struct.Demo_Fields=value,enabled",
                "struct.Demo_Fields.value=int32_t,0,0",
                "struct.Demo_Fields.enabled=bool,4,0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_write_r2_loader_plain(tmp_path):
    src = tmp_path / "types.sdbtxt"
    out = tmp_path / "types.r2"
    write_demo(src)

    count = write_r2_loader(src, out, progress_interval=0, quiet=True)
    text = out.read_text(encoding="utf-8")

    assert count == 14
    assert "tk Demo_o=struct\n" in text
    assert "tk struct.Demo_o.fields=Demo_Fields,16,0\n" in text
    assert "tk struct.Demo_Fields.enabled=bool,4,0\n" in text
    # Primitive fixups are appended even if records already existed, so the loader
    # repairs r2 sessions where imports clobbered primitive type records.
    assert "tk type.double.size=64\n" in text
    assert text.rstrip().endswith("e scr.utf8=true")
    assert "e scr.color=false\n" in text
    assert "e scr.color=1\n" in text
    assert "tk type.int32_t=d\n" in text
    assert "tk type.bool=b\n" in text


def test_write_r2_loader_can_skip_restore_settings(tmp_path):
    src = tmp_path / "types.sdbtxt"
    out = tmp_path / "types.r2"
    write_demo(src)

    write_r2_loader(src, out, progress_interval=0, quiet=True, restore_settings=False)
    text = out.read_text(encoding="utf-8")

    assert "e scr.color=false\n" in text
    assert "e scr.color=auto\n" not in text
    assert "e scr.utf8=true\n" not in text


def test_write_r2_loader_gzip(tmp_path):
    src = tmp_path / "types.sdbtxt"
    out = tmp_path / "types.r2.gz"
    write_demo(src)

    count = write_r2_loader(src, out, gzip_output=True, progress_interval=0, quiet=True)
    with gzip.open(out, "rt", encoding="utf-8") as fp:
        text = fp.read()

    assert count == 14
    assert "tk Demo_o=struct\n" in text
    assert "tk struct.Demo_Fields.value=int32_t,0,0\n" in text
