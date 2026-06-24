# gdt2r2sdb

`gdt2r2sdb` converts C headers or existing Ghidra `.gdt` data type archives into radare2 type SDB databases.

The Java Ghidra scripts are real files in this project, not Python string templates:

```text
src/gdt2r2sdb/ghidra_scripts/HeaderToGdt.java
src/gdt2r2sdb/ghidra_scripts/GdtToR2SdbText.java
```

The Python package copies those files into a temporary Ghidra script directory at runtime and invokes `analyzeHeadless`.

## Install

```sh
python3 -m pip install -e .
```

## Convert an IL2CPP header for ARM64

```sh
export GHIDRA_HOME="$HOME/Applications/ghidra_12.0.4_PUBLIC"
export GHIDRA_HEADLESS="$GHIDRA_HOME/support/analyzeHeadless"

gdt2r2sdb \
  --header out_il2cppdumper/il2cpp_ghidra.h \
  --out-gdt il2cpp.gdt \
  --out-sdbtxt il2cpp.sdbtxt \
  --out-sdb il2cpp.sdb \
  --sdb r2sdb \
  --arch arm64 \
  --bits 64 \
  --ghidra "$GHIDRA_HEADLESS"
```

Then in radare2:

```r2
tos ./il2cpp.sdb
ts Il2CppClass
tk~UnityEngine_MonoBehaviour_Fields
```

## Convert an existing GDT

```sh
gdt2r2sdb \
  --gdt il2cpp.gdt \
  --out-sdbtxt il2cpp.sdbtxt \
  --out-sdb il2cpp.sdb \
  --sdb r2sdb \
  --arch arm64 \
  --bits 64 \
  --ghidra "$GHIDRA_HEADLESS"
```

## Verify fields against the original header

```sh
gdt2r2sdb-verify out_il2cppdumper/il2cpp_ghidra.h --sdbtxt il2cpp.sdbtxt
```

A good result is:

```text
MISSING_STRUCTS=0
MISSING_UNIONS=0
FIELD_MISMATCHES=0
```

## Design constraints kept intentionally

This version is conservative:

- no `super` field flattening;
- no synthetic `ptr_*` aliases by default;
- no category/header filename prefixing;
- no repeated underscore collapsing;
- parser logs are off by default for speed;
- Ghidra headless is run with `-noanalysis` because the dummy program only exists to host scripts.

## Tests

Fast tests:

```sh
python3 -m pip install -e '.[test]'
pytest
```

Full local integration tests need Ghidra and radare2 tools:

```sh
export GHIDRA_HEADLESS="$HOME/Applications/ghidra_12.0.4_PUBLIC/support/analyzeHeadless"
pytest tests/test_integration_ghidra.py
```

## Real IL2CPP header regressions covered

The test fixture includes the failure modes from a real `il2cpp_ghidra.h` dump:

- anonymous unions inside `MethodInfo` are flattened into parent struct fields;
- `super` fields are preserved as normal fields;
- repeated underscores are preserved;
- struct names containing `UnsignedInteger` / `UnsignedLong` are not misclassified as primitive unsigned integers;
- Java scripts are packaged as real `.java` files, not embedded Python strings.

For a large real header, run:

```sh
GDT2R2SDB_REAL_HEADER=/path/to/il2cpp_ghidra.h pytest
```

and after conversion:

```sh
gdt2r2sdb-verify /path/to/il2cpp_ghidra.h --sdbtxt il2cpp.sdbtxt
```

Expected target:

```text
MISSING_STRUCTS=0
MISSING_UNIONS=0
FIELD_MISMATCHES=0
```
