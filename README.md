# gdt2sdb

`gdt2sdb` converts C headers or existing Ghidra `.gdt` data type archives into radare2 type SDB databases.

The Java Ghidra scripts in this project:
```text
src/gdt2r2sdb/ghidra_scripts/HeaderToGdt.java
src/gdt2r2sdb/ghidra_scripts/GdtToR2SdbText.java
```

The Python package copies those files into a temporary Ghidra script directory at runtime and invokes `analyzeHeadless`.

## Install

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Convert an IL2CPP header for ARM64 (Requires Ghidra)

```sh
export GHIDRA_HOME="$HOME/Applications/ghidra_12.0.4_PUBLIC"
export GHIDRA_HEADLESS="$GHIDRA_HOME/support/analyzeHeadless"

gdt2sdb \
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



## radare2 loader scripts for huge SDBs

Some radare2 versions can read a huge compiled `.sdb` with `r2sdb`, but `tos ./il2cpp.sdb` may fail to expose every key through `tk`/`ts` after loading. In that case, generate a plain r2 script that recreates the same type database with `tk key=value` commands and bypasses the `tos` import path:

```sh
gdt2sdb-r2loader \
  --sdbtxt il2cpp.sdbtxt \
  --out-r2 il2cpp_types.r2
```

Load it from the r2 command line:

```sh
r2 -q -i il2cpp_types.r2 libil2cpp.so
```

or inside an existing r2 session:

```r2
. ./il2cpp_types.r2
```

The loader script appends primitive re-prime commands such as `tk type.int32_t=d` and `tk type.bool=b`, because `to`/`tos` style imports may leave primitive records missing or overwritten in some r2 sessions. It temporarily disables `scr.color` and `scr.utf8` while loading so progress output stays plain, then restores interactive-friendly values at the end with `e scr.color=auto` and `e scr.utf8=true`. Use `--no-restore-settings` if you do not want those footer commands.

For smaller files on disk, write a compressed loader:

```sh
gdt2sdb-r2loader \
  --sdbtxt il2cpp.sdbtxt \
  --out-r2 il2cpp_types.r2.gz \
  --gzip
```

Compressed loaders are intended for storage/transport. Decompress to a real temporary `.r2` file before loading; piping or shell process substitution can hit r2 input-size/path issues with very large scripts:

```sh
tmp="$(mktemp --suffix=.r2)"
gzip -dc il2cpp_types.r2.gz > "$tmp"
r2 -q -i "$tmp" libil2cpp.so
rm -f "$tmp"
```

This avoids the `tos` path, but it does not remove radare2's `tp`/`pf` format-string limits for very large nested structs. If `tp SomeClass_o` expands too much, print the field payload directly instead, for example `tp SomeClass_Fields @ object_address + 0x10` for normal 64-bit IL2CPP objects.

## r2-friendly subset SDBs for huge IL2CPP databases

For very large IL2CPP projects, radare2 may load the compiled `.sdb` but fail to expose every key through `tos`/`tk`, or `ts` may return a truncated/blank print format for a specific large object. The full `il2cpp.sdbtxt` remains the source of truth; use `gdt2sdb-subset` to build a small dependency slice for the root type you want to inspect interactively.

```sh
gdt2sdb-subset \
  --sdbtxt il2cpp.sdbtxt \
  --root SomeController_o \
  --out-sdbtxt SomeController.subset.sdbtxt \
  --out-sdb SomeController.subset.sdb \
  --sdb r2sdb
```

Then in radare2:

```r2
tos ./SomeController.subset.sdb
ts SomeController_o
tp SomeController_o @ 0xADDRESS
```

The subset command follows by-value struct/union fields recursively and keeps pointer targets shallow by default, which is usually enough for r2 to print pointer fields as `p`. Use `--follow-pointers` only when you explicitly want pointer target layouts copied too.

## Convert an existing GDT

```sh
gdt2sdb \
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
gdt2sdb-verify out_il2cppdumper/il2cpp_ghidra.h --sdbtxt il2cpp.sdbtxt
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
gdt2sdb-verify /path/to/il2cpp_ghidra.h --sdbtxt il2cpp.sdbtxt
```

Expected target:

```text
MISSING_STRUCTS=0
MISSING_UNIONS=0
FIELD_MISMATCHES=0
```
