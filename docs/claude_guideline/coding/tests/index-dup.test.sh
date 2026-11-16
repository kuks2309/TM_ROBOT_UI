#!/usr/bin/env bash
# index-dup.test.sh — 표 중복 차단 계약 (⟦CI:index-dup⟧).
#
# 계약의 축은 **중복 여부**다. 루트 `docs/` 표 자체가 나쁜 것이 아니라, 모듈 표가 따로
# 있는데 루트에도 같은 종류가 있는 상태가 나쁘다(그게 모든 세션이 쓰는 단 하나의 파일이 된다).
# 단일 모듈 저장소에서는 루트 표가 곧 권위본이므로 통과해야 한다 — 음성 대조로 잡는다.
#
# 실행: bash coding/tests/index-dup.test.sh
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHK="$DIR/../checks/index-dup.sh"
PASS=0; FAIL=0; T=""; OUT=""; RC=0

# 없는 헬퍼를 부르면 실패로 셈한다. 핸들러는 서브셸에서 돌아 변수 증가가 사라지므로
# (bash 사양) 마커 파일을 쓴다 — 단언이 조용히 사라지는 사고를 막는다.
MARK="$(mktemp)"
trap 'rm -f "$MARK"; [ -n "$T" ] && rm -rf "$T"' EXIT
command_not_found_handle() {
  printf '  ✗ 정의되지 않은 헬퍼 호출: %s\n' "$1"; echo "$1" >> "$MARK"; return 127
}

setup()    { T="$(mktemp -d)"; OUT="$T/.out"; }
teardown() { [ -n "$T" ] && rm -rf "$T"; T=""; }

tbl() {  # tbl <상대경로> <행내용>
  mkdir -p "$T/$(dirname "$1")"
  printf '| # | 함수 |\n|---|---|\n| 1 | `%s` |\n' "$2" > "$T/$1"
}
check_dup() { bash "$CHK" "$T" > "$OUT" 2>&1; RC=$?; }
merge()     { bash "$CHK" --merge "$T" > "$OUT" 2>&1; RC=$?; }

rc_is() { if [ "$2" = "$3" ]; then printf '  ✓ %s\n' "$1"; PASS=$((PASS+1));
          else printf '  ✗ %s — 기대 RC %s, 실제 %s. 출력:\n%s\n' "$1" "$2" "$3" \
               "$(sed 's/^/      /' "$OUT")"; FAIL=$((FAIL+1)); fi; }
has()   { if grep -qF -- "$2" "$OUT" 2>/dev/null; then printf '  ✓ %s\n' "$1"; PASS=$((PASS+1));
          else printf '  ✗ %s — "%s" 없음. 실제:\n%s\n' "$1" "$2" \
               "$(sed 's/^/      /' "$OUT")"; FAIL=$((FAIL+1)); fi; }
hasnt() { if grep -qF -- "$2" "$OUT" 2>/dev/null; then printf '  ✗ %s — "%s" 있음\n' "$1" "$2"; FAIL=$((FAIL+1));
          else printf '  ✓ %s\n' "$1"; PASS=$((PASS+1)); fi; }

echo "D1  모듈 표 2개 + 루트 표 → 중복으로 차단"
setup
tbl src/a/docs/function_table.md f
tbl src/b/docs/function_table.md g
mkdir -p "$T/docs"; printf '| 패키지 | 수 |\n|---|---|\n| a | 1 |\n| b | 1 |\n' > "$T/docs/function_table.md"
check_dup; rc_is "차단" 1 "$RC"
has "중복 파일 지목"  "docs/function_table.md"
has "충돌 이유 설명"  "맞붙은 행"
has "대안 제시"       "--merge"
teardown

echo "D2  루트 표를 지우면 통과"
setup
tbl src/a/docs/function_table.md f
tbl src/b/docs/function_table.md g
check_dup; rc_is "통과" 0 "$RC"
has "모듈 표 2개 인식" "모듈 표 2"
teardown

echo "D3  단일 모듈 저장소 — 루트 표가 권위본이므로 통과 (음성 대조)"
setup
mkdir -p "$T/docs"; printf '| # | 함수 |\n|---|---|\n| 1 | `f` |\n' > "$T/docs/function_table.md"
check_dup; rc_is "통과" 0 "$RC"
teardown

echo "D4  설치된 규칙 문서(claude_guideline)는 표 후보 아님 (음성 대조)"
setup
tbl src/a/docs/function_table.md f
tbl src/b/docs/function_table.md g
mkdir -p "$T/docs/claude_guideline/coding/docs"
printf '| # | 함수 |\n|---|---|\n| 1 | `x` |\n' > "$T/docs/claude_guideline/coding/docs/function_table.md"
check_dup; rc_is "통과" 0 "$RC"
hasnt "규칙 문서 미지목" "claude_guideline"
teardown

echo "D4b docs/ 안에 사는 코드의 모듈 표는 집계가 아니다 (음성 대조 — 실측 오탐 회귀)"
setup
tbl src/a/docs/function_table.md f
tbl src/b/docs/function_table.md g
# docs/relocation/scripts/ 안에 코드가 있고 그 표가 거기 있는 경우(LGIT-C6-Cobot 실측).
# docs/ 하위 전체를 뒤지면 이것을 집계로 오판해 커밋을 막는다.
tbl docs/relocation/scripts/function_table.md reloc
check_dup; rc_is "통과" 0 "$RC"
hasnt "nested 표 미지목" "relocation"
teardown

echo "D5  전역변수표·토픽표도 같은 규칙"
setup
tbl src/a/docs/global_variable_table.md v1
tbl src/b/docs/global_variable_table.md v2
mkdir -p "$T/docs"; printf '| 패키지 | 수 |\n|---|---|\n| a | 1 |\n' > "$T/docs/global_variable_table.md"
check_dup; rc_is "변수표 중복 차단" 1 "$RC"
teardown
setup
tbl src/a/docs/topic_table.md t1
tbl src/b/docs/topic_table.md t2
mkdir -p "$T/docs"; printf '| 토픽 | 타입 |\n|---|---|\n| /a | X |\n' > "$T/docs/topic_table.md"
check_dup; rc_is "토픽표 중복 차단" 1 "$RC"
teardown

echo "D6  --merge 는 모듈 표를 모아 내고, 생성물임을 밝힌다"
setup
tbl src/a/docs/function_table.md alpha
tbl src/b/docs/function_table.md beta
merge; rc_is "성공" 0 "$RC"
has "생성물 고지"     "커밋하지 않는다"
has "모듈 a 포함"     "src/a/docs/function_table.md"
has "모듈 b 포함"     "src/b/docs/function_table.md"
has "원본 행 포함"    "alpha"
teardown

echo "D7  표가 없으면 합칠 것이 없다 (음성 대조)"
setup; merge; rc_is "통과" 0 "$RC"; has "안내" "합칠 것이 없다"; teardown

echo
if [ -s "$MARK" ]; then
  echo "✗ 정의되지 않은 헬퍼 $(wc -l < "$MARK") 회 호출 — 그만큼 단언이 사라졌다:"
  sort -u "$MARK" | sed 's/^/    /'
  FAIL=$((FAIL + 1))
fi
if [ "$FAIL" -eq 0 ]; then echo "✓ 전체 통과 ($PASS)"; exit 0
else echo "✗ 실패 $FAIL / 통과 $PASS"; exit 1; fi
