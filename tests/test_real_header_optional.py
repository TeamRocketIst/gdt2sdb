import os
from pathlib import Path

import pytest

from gdt2r2sdb.verify import strip_comments, parse_struct_fields


@pytest.mark.skipif(not os.environ.get("GDT2R2SDB_REAL_HEADER"), reason="GDT2R2SDB_REAL_HEADER not set")
def test_real_il2cpp_header_expected_problem_cases():
    header = Path(os.environ["GDT2R2SDB_REAL_HEADER"])
    structs, unions = parse_struct_fields(strip_comments(header.read_text(errors="replace")))
    assert len(structs) > 20000
    assert structs["MethodInfo"] == [
        "methodPointer", "virtualMethodPointer", "invoker_method", "name", "klass",
        "return_type", "parameters", "rgctx_data", "methodMetadataHandle",
        "genericMethod", "genericContainerHandle", "token", "flags", "iflags", "slot",
        "parameters_count", "bitflags",
    ]
    for name in [
        "UnityEngine_UIElements_UnsignedIntegerField_UxmlFactory_Fields",
        "UnityEngine_UIElements_UnsignedLongField_UxmlFactory_Fields",
        "UnityEngine_UIElements_UxmlFactory_UnsignedIntegerField__UnsignedIntegerField_UxmlTraits__Fields",
        "UnityEngine_UIElements_UxmlFactory_UnsignedLongField__UnsignedLongField_UxmlTraits__Fields",
        "UnityEngine_UIElements_UxmlUnsignedIntAttributeDescription___c_Fields",
        "UnityEngine_UIElements_UxmlUnsignedLongAttributeDescription___c_Fields",
    ]:
        assert name in structs
