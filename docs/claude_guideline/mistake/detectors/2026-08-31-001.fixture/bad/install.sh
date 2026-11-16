#!/usr/bin/env bash
for d in "$@"; do
  if [ -f "$SRC/domains/$d.md" ]; then cp "$SRC/domains/$d.md" "$DEST/"
  else echo "  ! 도메인 스킵: $d"; fi
done
