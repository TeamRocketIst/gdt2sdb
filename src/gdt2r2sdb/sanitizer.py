from __future__ import annotations

import re
from textwrap import dedent

_STRUCT_DECL_RE = re.compile(r"\bstruct\s+([A-Za-z_][A-Za-z0-9_]*)\s*;")
_STRUCT_DEF_RE = re.compile(r"\bstruct\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{")
_TYPEDEF_STRUCT_RE = re.compile(r"\btypedef\s+struct\s+([A-Za-z_][A-Za-z0-9_]*)\b")


def discover_struct_names(text: str) -> list[str]:
    """Return struct names declared/defined in a generated C header, preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for rx in (_STRUCT_DECL_RE, _STRUCT_DEF_RE, _TYPEDEF_STRUCT_RE):
        for m in rx.finditer(text):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                out.append(name)
    return out


def make_forward_typedef_prelude(text: str) -> str:
    """Add C-compatible typedefs for `struct Foo;` so IL2CPP `Foo*` parses as C.

    Il2CppDumper-style dumps often write:
      struct MethodInfo;
      const MethodInfo* method;

    That is C++-style usage. Ghidra's C parser is happier if we inject:
      typedef struct MethodInfo MethodInfo;
    """
    lines: list[str] = []
    for name in discover_struct_names(text):
        lines.append(f"typedef struct {name} {name};")
    return "\n".join(lines) + ("\n" if lines else "")


def sanitize_header_text(text: str, *, inject_forward_typedefs: bool = True) -> str:
    """Make common IL2CPP/MSVC-ish generated headers easier for Ghidra's C parser."""
    replacements = [
        (r"\bunsigned\s+__int8\b", "unsigned char"),
        (r"\bunsigned\s+__int16\b", "unsigned short"),
        (r"\bunsigned\s+__int32\b", "unsigned int"),
        (r"\bunsigned\s+__int64\b", "unsigned long long"),
        (r"\b__int8\b", "signed char"),
        (r"\b__int16\b", "short"),
        (r"\b__int32\b", "int"),
        (r"\b__int64\b", "long long"),
        (r"\b__cdecl\b|\b__stdcall\b|\b__fastcall\b|\b__thiscall\b|\b__vectorcall\b", ""),
        (r"\b__declspec\s*\([^)]*\)", ""),
        (r"\b__attribute__\s*\(\([^)]*\)\)", ""),
    ]
    for pat, repl in replacements:
        text = re.sub(pat, repl, text)

    prelude = dedent(
        """
        /* gdt2r2sdb generated prelude for parser compatibility. */
        #ifndef GDT2R2SDB_PRELUDE
        #define GDT2R2SDB_PRELUDE 1
        #ifndef __cplusplus
        typedef unsigned char bool;
        #endif
        #ifndef true
        #define true 1
        #endif
        #ifndef false
        #define false 0
        #endif
        """
    ).strip() + "\n"
    if inject_forward_typedefs:
        prelude += make_forward_typedef_prelude(text)
    prelude += "#endif\n\n"
    return prelude + text


def clean_name_for_sdb(name: str | None) -> str:
    """Python mirror of the Java cleanName: preserve repeated/leading underscores."""
    if name is None:
        return ""
    s = name.strip()
    s = re.sub(r"^(struct|union|enum)\s+", "", s)
    s = s.replace("::", "_").replace(".", "_").replace("/", "_").replace("$", "_")
    s = re.sub(r"[^A-Za-z0-9_]", "_", s)
    if not s:
        s = "anon"
    if s[0].isdigit():
        s = "_" + s
    return s
