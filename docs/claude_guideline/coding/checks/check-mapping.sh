#!/usr/bin/env bash
# check-mapping.sh — 메타 불변식: 번들 마크다운의 ⟦CI:<id>⟧ 태그 ↔ checks/<id>.sh 1:1 정합.
# 번들이 '자기 강제력'에 대해 거짓말 못 하게 한다.
#   - 태그가 약속한 스크립트가 없으면(빈 약속)  → 실패
#   - 스크립트가 어느 태그에도 안 걸리면(고아)   → 실패
# 스캔 대상: 코어(coding.md)·stack.md·conventions.md·domains/*.md (모든 규칙 마크다운).
# placeholder ⟦CI:<id>⟧ 는 <id> 가 [a-z] 로 시작 안 하므로 자동 제외.
# id 에 숫자 허용 — ros2-qos 처럼 도메인 이름에 숫자가 든다.
# 일반 ⟦CI⟧(:id 없음)도 매칭 안 됨 — '후보(미구현)' 표기에 안전.
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$DIR/.."

# 스캔할 규칙 마크다운 수집 (존재하는 것만)
files=()
for f in "$SRC"/coding.md "$SRC"/stack.md "$SRC"/conventions.md "$SRC"/domains/*.md; do
  [ -f "$f" ] && files+=("$f")
done
[ "${#files[@]}" -gt 0 ] || { echo "오류: 규칙 마크다운 없음: $SRC"; exit 2; }

# 1) 약속한 태그 id (실제 id 만; <id> placeholder 제외)
tags=$(grep -hoE '⟦CI:[a-z][a-z0-9-]*⟧' "${files[@]}" 2>/dev/null | sed -E 's/^⟦CI:(.*)⟧$/\1/' | sort -u)

fail=0

# 2) 태그 → 백킹 스크립트 존재?
for id in $tags; do
  if [ ! -f "$DIR/$id.sh" ]; then
    echo "✗ 빈 약속: 태그 ⟦CI:$id⟧ 가 가리키는 checks/$id.sh 가 없음"
    fail=1
  fi
done

# 3) 스크립트 → 태그에 참조됨? (자기 자신 제외)
for f in "$DIR"/*.sh; do
  base=$(basename "$f" .sh)
  [ "$base" = "check-mapping" ] && continue
  if ! printf '%s\n' "$tags" | grep -qx "$base"; then
    echo "✗ 고아 스크립트: checks/$base.sh 가 어느 ⟦CI⟧ 태그에도 안 걸림"
    fail=1
  fi
done

# ── ⟦훅:<id>⟧ ↔ hooks/coding-<id>.py ────────────────────────────────────────
# 훅은 '도구 호출 시점 차단'이라 CI 와 강제 종류가 다르지만, 번들이 자기 강제력을
# 거짓 신고하면 안 되는 것은 같다. 태그 없는 훅(번들 전역 목적)은 아래 목록에만 허용 —
# 새 훅을 무태그로 추가하면 실패시켜 '태그를 달지, 예외로 둘지' 판단을 강제한다.
HOOKS_DIR="$SRC/hooks"
UNTAGGED_OK="coding-reminder.py"

htags=$(grep -hoE '⟦훅:[a-z][a-z0-9-]*⟧' "${files[@]}" 2>/dev/null | sed -E 's/^⟦훅:(.*)⟧$/\1/' | sort -u)

for id in $htags; do
  if [ ! -f "$HOOKS_DIR/coding-$id.py" ]; then
    echo "✗ 빈 약속: 태그 ⟦훅:$id⟧ 가 가리키는 hooks/coding-$id.py 가 없음"
    fail=1
  fi
done

if [ -d "$HOOKS_DIR" ]; then
  for f in "$HOOKS_DIR"/*.py; do
    [ -f "$f" ] || continue
    base=$(basename "$f")
    case " $UNTAGGED_OK " in *" $base "*) continue ;; esac
    id="${base#coding-}"; id="${id%.py}"
    if ! printf '%s\n' "$htags" | grep -qx "$id"; then
      echo "✗ 무태그 훅: hooks/$base 가 어느 ⟦훅⟧ 태그에도 안 걸림 (태그를 달거나 UNTAGGED_OK 에 등재)"
      fail=1
    fi
  done
fi

n=$(printf '%s\n' "$tags" | grep -c .)
hn=$(printf '%s\n' "$htags" | grep -c .)
if [ "$fail" -eq 0 ]; then
  echo "✓ 강제 정합: ⟦CI⟧ ↔ checks/*.sh ($n 개) · ⟦훅⟧ ↔ hooks/coding-*.py ($hn 개), 코어+도메인 스캔"
else
  echo "— 약속된 태그: CI $n 개 [$(echo "$tags" | tr '\n' ' ')] · 훅 $hn 개 [$(echo "$htags" | tr '\n' ' ')]"
fi
exit $fail
