#!/usr/bin/env bash
# 2026-10-20-001 — 커밋 메시지 트레일러의 이메일이 깨진 채 커밋·push.
#
# `Co-Authored-By: … <noreply@antml:thinking_mode>` 처럼 `<…>` 안이 이메일 형식이 아닌 트레일러를
# 단 커밋 3 건이 즉시 safepush 로 origin/main 에 올라갔다(590fe07·7898228·7c1050a). heredoc 으로
# 메시지를 쓸 때 눈으로만 확인했고, 커밋 전·push 전 어디에도 트레일러 형식 검사가 없었다.
# push 된 뒤에는 force-push 없이 고칠 수 없다.
#
# 잡는 것 — 트레일러 키(Co-Authored-By·Signed-off-by·Reviewed-by·Acked-by·Reported-by·Tested-by)
#   줄의 값이 `이름 <local@domain.tld>` 형식이 아닌 것.
#   ① 스캔루트 아래 커밋 메시지 파일: `COMMIT_EDITMSG`, `*.commitmsg` (.git·*.fixture 제외)
#   ② 스캔루트 **직속** git 저장소(`<루트>/.git` 실재)의 아직 push 되지 않은 커밋(`@{u}..HEAD`,
#      upstream 없으면 HEAD 1건). push 된 이력은 보지 않는다 — 고칠 수 없는 것을 영구 실패로
#      두면 검사가 무시된다. 직속으로 한정하는 것은 표본 디렉터리에서 상위 저장소로 새지 않기 위함.
set -uo pipefail
R="${1:-.}"
R="$(cd "$R" 2>/dev/null && pwd)" || { echo "오류: 경로 없음: $1"; exit 2; }

KEYS='Co-Authored-By|Co-authored-by|Signed-off-by|Reviewed-by|Acked-by|Reported-by|Tested-by'
EMAIL='<[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}>[[:space:]]*$'
hits=""
add() { hits="$hits$1"$'\n'; }

check_text() {  # check_text <라벨> <메시지 본문>
  local label="$1" n=0 line
  while IFS= read -r line; do
    n=$((n + 1))
    if printf '%s' "$line" | grep -qE "^($KEYS):"; then
      printf '%s' "$line" | grep -qE "$EMAIL" || add "$label:$n: 트레일러 이메일 형식 아님 → $line"
    fi
  done <<< "$2"
}

# ① 커밋 메시지 파일
while IFS= read -r f; do
  [ -n "$f" ] || continue
  check_text "$f" "$(cat "$f")"
done < <(find "$R" \( -type d \( -name .git -o -name node_modules -o -name '*.fixture' \) -prune \) -o \
              \( -type f \( -name COMMIT_EDITMSG -o -name '*.commitmsg' \) -print \) 2>/dev/null | sort)

# ② 아직 push 되지 않은 커밋 (루트 직속 저장소만)
if [ -e "$R/.git" ]; then
  if git -C "$R" rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then range='@{u}..HEAD'; else range='-1 HEAD'; fi
  while IFS= read -r h; do
    [ -n "$h" ] || continue
    check_text "commit $h" "$(git -C "$R" log -1 --format=%B "$h")"
  done < <(git -C "$R" log --format=%h $range 2>/dev/null)
fi

[ -z "$hits" ] && exit 0
printf '%s' "$hits"
exit 1
