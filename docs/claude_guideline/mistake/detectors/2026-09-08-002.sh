#!/usr/bin/env bash
# 2026-09-08-002 — 음성 대조 표본이 없거나 죽어 있는 검사기.
#
# `checks/`·`detectors/` 아래 검사 스크립트는 자기 표본(`<이름>.fixture/bad/`)을 가져야 하고,
# 그 표본에서 **실제로 걸려야** 한다. 표본이 없으면 그 검사가 무엇을 잡고 무엇을 놓치는지
# 아무도 모르고, 표본이 있어도 죽어 있으면 "통과"가 "검증됨"으로 읽힌다.
#   실측 ①: issue_fix v1.1.0 의 grep 2 개가 오탐 1·우회 2 를 안은 채 출하됐다.
#   실측 ②: 이 검사의 첫 판은 표본의 존재만 봤고, mistake.md 부재로 exit 2 인 죽은 표본을
#           그대로 통과시켰다. 손으로 돌려서야 드러났다.
#
# 잡는 것
#   ① 표본 없음   — `<이름>.fixture/bad/` 부재 또는 빈 디렉토리(빈 디렉토리 우회 포함)
#   ② 죽은 표본   — bad 표본에서 exit 1 이 아님
#   ③ 과잉 검사   — good 표본이 있는데 거기서 exit 0 이 아님
#
# 실행 방식 — 표본 구조가 곧 선언이다(별도 선언 파일 없음)
#   · `<이름>.fixture/<판>/checks/<이름>.sh` 사본이 있으면 그 **사본을 인자 없이** 돌린다.
#     자기 위치로 SRC 를 정하는 검사용(예: check-mapping.sh).
#   · 없으면 원본을 `<이름>.sh <표본경로>` 로 돌린다(스캔루트 인자형).
#
# 돌리는 대상은 **표본을 갖춘 검사뿐**이다 — 표본을 쓴 저자가 실행을 허용한 것으로 본다.
# 표본 없는 검사는 ①로 보고만 하고 실행하지 않는다(부작용 있는 검사 보호).
set -uo pipefail
R="${1:-.}"
R="$(cd "$R" 2>/dev/null && pwd)" || { echo "오류: 경로 없음: $1"; exit 2; }
TMO=30

hits=""
add() { hits="$hits$1"$'\n'; }

run_case() {  # run_case <원본> <표본판경로> <이름> → exit code 출력
  local s="$1" fx="$2" name="$3" copy="$2/checks/$3.sh"
  if [ -f "$copy" ]; then timeout "$TMO" bash "$copy" >/dev/null 2>&1
  else timeout "$TMO" bash "$s" "$fx" >/dev/null 2>&1; fi
  echo $?
}

while IFS= read -r s; do
  base="${s%.sh}"; name="$(basename "$base")"; fx="$base.fixture"
  if ! find "$fx/bad" -type f -print -quit 2>/dev/null | grep -q .; then
    add "$s:1: 음성 대조 표본 없음 → $name.fixture/bad/ 에 재현 표본 필요"
    continue
  fi
  rc="$(run_case "$s" "$fx/bad" "$name")"
  [ "$rc" = "1" ] || add "$s:1: 죽은 표본 → $name.fixture/bad 에서 exit $rc (1 이어야)"
  if [ -d "$fx/good" ]; then
    rcg="$(run_case "$s" "$fx/good" "$name")"
    [ "$rcg" = "0" ] || add "$s:1: 과잉 검사 → $name.fixture/good 에서 exit $rcg (0 이어야)"
  fi
done < <(find "$R" \
            \( -type d \( -name '*.fixture' -o -name .git -o -name node_modules \) -prune \) -o \
            \( -type f -name '*.sh' -print \) 2>/dev/null \
          | grep -E '/(checks|detectors)/[^/]+\.sh$' \
          | grep -vE '/(run|install)\.sh$' \
          | sort)

[ -z "$hits" ] && exit 0
printf '%s' "$hits"
exit 1
