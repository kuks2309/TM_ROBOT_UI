#!/usr/bin/env bash
# index-dup.sh — 표의 **중복 사본**을 재도출해 차단 (⟦CI:index-dup⟧).
#
# 잡는 것: 모듈 로컬 표(권위본)가 2개 이상 있는데 저장소 루트 `docs/` 직속에도 같은 종류의
# 표가 커밋돼 있는 상태. 그 루트 표는 모듈 표들의 **중복 사본**이다.
#
# 왜 차단하나 — 루트 사본은 **모든 세션이 쓰는 단 하나의 파일**이 된다. 패키지마다 요약
# 한 행이라, 세션이 각자 자기 행만 고쳐도 git 은 맞붙은 줄을 한 덩어리로 보므로 rebase
# 재생에서 충돌한다. 실측(2026-10-22 재현): 36·37줄 충돌, 36·38줄은 자동 병합 — **바로
# 맞붙은 한 쌍만** 부딪힌다. 패키지가 늘면 맞붙은 쌍이 늘어 빈도가 올라간다. 실사격에서
# 같은 두 행이 두 번 충돌했다.
#
# 규율로는 못 막는다 — "각자 자기 행만 고친다" 는 이미 지켜졌는데도 충돌했다. 고치는 동안
# 상대가 push 하면 재생 시점에 부딪히므로, 순차 처리는 서로 **기다릴 때만** 성립한다.
#
# 중복을 없애도 정보는 잃지 않는다. 모듈 표가 원본이고 커밋되며, 교차 조회는 `--merge` 로
# 그 자리에서 합쳐 본다(생성물이라 커밋하지 않는다).
#
# 단일 모듈 저장소는 대상이 아니다 — 그 `docs/` 표가 곧 모듈 표이고 중복이 아니다.
#
# 용법: index-dup.sh [스캔루트]            # 검사
#       index-dup.sh --merge [스캔루트]    # 교차 조회 합본을 stdout 으로
set -uo pipefail

MERGE=0
if [ "${1:-}" = "--merge" ]; then MERGE=1; shift; fi
R="${1:-.}"
[ -d "$R" ] || { echo "오류: 경로 없음: $R"; exit 2; }

TABLE_NAMES='function_table.md|global_variable_table.md|topic_table.md|inventory.md|함수표.*\.md|전역변수표.*\.md|토픽표.*\.md'

# 모듈 로컬 표 — 저장소 루트 바로 아래 docs/ 가 아닌 곳의 표(권위본).
module_tables() {
  find "$R" -type f -regextype posix-egrep -regex ".*/($TABLE_NAMES)" \
       -not -path '*/.git/*' -not -path '*/claude_guideline/*' \
       -not -path '*.fixture/*' -not -path '*/node_modules/*' 2>/dev/null \
    | grep -vE "^$R/docs/" | sort
}

# 루트 직속 표 — `docs/<이름>.md` **딱 한 단계**만. 집계본이 사는 자리다.
# `docs/` 하위 전체를 뒤지면 `docs/<무엇>/scripts/function_table.md` 처럼 **docs 안에 있는
# 코드의 모듈 표**까지 집계로 오판한다(실측: LGIT-C6-Cobot 의
# `docs/relocation/scripts/function_table.md` — 집계본이 아니라 그 스크립트들의 권위본).
# 커밋을 막는 이빨이라 오탐이 곧 차단이므로 보수적으로 좁힌다 — 깊은 자리의 집계본은
# 놓치되(미탐), 모듈 표를 집계로 몰아 작업을 막지는 않는다.
root_tables() {
  find "$R/docs" -maxdepth 1 -type f -regextype posix-egrep -regex ".*/($TABLE_NAMES)" \
       2>/dev/null | sort
}

# 교차 조회 합본 — 모듈 표를 모아 stdout 으로. 커밋 대상 아님.
merge_view() {
  echo "# 교차 조회 합본 (생성물 — 커밋하지 않는다)"
  echo
  echo "> \`checks/index-dup.sh --merge\` 로 그 자리에서 만든 것이다. 권위본은 각 모듈의 표다."
  echo
  local f
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    printf '## %s\n\n' "${f#$R/}"
    sed -n '/^|/,$p' "$f" | head -200
    echo
  done
}

MODS="$(module_tables)"
N_MOD="$(printf '%s\n' "$MODS" | grep -c . || true)"

if [ "$MERGE" = 1 ]; then
  [ "$N_MOD" -gt 0 ] || { echo "· 모듈 표 없음 — 합칠 것이 없다"; exit 0; }
  printf '%s\n' "$MODS" | merge_view
  exit 0
fi

ROOTS="$(root_tables)"
N_ROOT="$(printf '%s\n' "$ROOTS" | grep -c . || true)"

# 단일 모듈 저장소(모듈 표 0~1개)에서는 루트 표가 곧 권위본이다 — 중복이 아니다.
if [ "$N_MOD" -lt 2 ] || [ "$N_ROOT" -eq 0 ]; then
  echo "✓ 표 중복 없음 (모듈 표 $N_MOD · 루트 직속 $N_ROOT)"
  exit 0
fi

echo "✗ [표 중복] 모듈 표 $N_MOD 개가 있는데 루트 직속에도 표가 있습니다 — 중복 사본입니다:"
printf '%s\n' "$ROOTS" | sed "s|^$R/|      |"
echo "   → 루트 사본은 모든 세션이 쓰는 단 하나의 파일이라 맞붙은 행끼리 충돌합니다."
echo "   → 삭제하십시오. 교차 조회는 \`checks/index-dup.sh --merge\` 로 그 자리에서 만듭니다."
exit 1
