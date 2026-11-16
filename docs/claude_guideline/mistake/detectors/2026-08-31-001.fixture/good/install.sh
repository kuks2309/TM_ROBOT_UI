#!/usr/bin/env bash
for d in "$@"; do
  [ -f "$SRC/domains/$d.md" ] || BAD="$BAD $d"
done
[ -n "$BAD" ] && { echo "오류: 이 번들에 없는 도메인:$BAD"; exit 2; }
for d in "$@"; do cp "$SRC/domains/$d.md" "$DEST/"; done
