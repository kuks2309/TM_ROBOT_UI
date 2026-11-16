#!/usr/bin/env bash
# update-entry.sh — `code_updates/` entry 형식을 재도출해 차단 (⟦CI:update-entry⟧).
#
# 잡는 것 둘:
#   1) **정정문 덧붙임** — `## 후속`·`## 정정`·`## 추가로 발견` 류가 entry 아래에 쌓인 것.
#      entry 는 그 변경의 **현재 사실**을 적는 문서다. 경과를 시간순으로 쌓으면 "무엇이
#      사실인가" 가 아니라 "내가 어떤 순서로 알게 됐는가" 가 된다. 틀린 기록은 지우고
#      다시 쓴다 — entry 를 통째로 교체한다(conventions.md §4).
#   2) **필수 항목 누락** — 대상·변경·사유 3개. 무엇을 왜 바꿨는지 없는 기록은 기록이 아니다.
#
# 대상: 인자 경로 아래 모든 `code_updates/*.md` (README.md 제외).
# 용법: update-entry.sh [스캔루트]
set -uo pipefail
R="${1:-.}"
[ -d "$R" ] || { echo "오류: 경로 없음: $R"; exit 2; }

fail=0
n=0
while IFS= read -r f; do
  n=$((n + 1))
  base="$(basename "$f")"
  # 덧붙인 정정 절
  hits="$(grep -nE '^#{2,3} *(후속|정정|추가로 발견|보완|덧붙|같이 잡힌|배포 중 잡힌|나중에 잡힌|추가 발견)' "$f" 2>/dev/null || true)"
  if [ -n "$hits" ]; then
    printf '✗ [정정 덧붙임] %s\n' "$f"
    printf '%s\n' "$hits" | sed 's/^/      /'
    printf '      → 이 entry 를 통째로 다시 쓰십시오(정정문을 쌓지 않는다).\n'
    fail=1
  fi
  # 필수 항목
  miss=""
  for k in 대상 변경 사유; do
    grep -qE "^[-*] *\*{0,2}$k\*{0,2} *:" "$f" 2>/dev/null || miss="$miss $k"
  done
  if [ -n "$miss" ]; then
    printf '✗ [필수 항목 누락] %s —%s\n' "$f" "$miss"
    fail=1
  fi
done < <(find "$R" -path '*/code_updates/*.md' -not -name README.md \
              -not -path '*/.git/*' -not -path '*.fixture/*' 2>/dev/null | sort)

if [ "$fail" -eq 0 ]; then
  echo "✓ code_updates entry $n 개 형식 통과 ($R)"
fi
exit $fail
