#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: $0 path/to/il2cpp_ghidra.h output-prefix [ghidra-headless]" >&2
  exit 2
fi

HEADER="$1"
OUT="$2"
GHIDRA="${3:-${GHIDRA_HEADLESS:-$HOME/Applications/ghidra_12.0.4_PUBLIC/support/analyzeHeadless}}"

gdt2r2sdb \
  --header "$HEADER" \
  --out-gdt "${OUT}.gdt" \
  --out-sdbtxt "${OUT}.sdbtxt" \
  --out-sdb "${OUT}.sdb" \
  --sdb "${SDB:-r2sdb}" \
  --arch arm64 \
  --bits 64 \
  --ghidra "$GHIDRA"

gdt2r2sdb-verify "$HEADER" --sdbtxt "${OUT}.sdbtxt"

echo "load in r2 with: tos ${OUT}.sdb"
