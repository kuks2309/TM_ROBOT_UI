#!/usr/bin/env bash
# comment-gate.test.sh — coding-comment-gate.py 계약 테스트.
#
# 훅 계약(Claude Code PostToolUse): stdin JSON → stdout 에
#   {"decision":"block","reason":...} = 모델에게 교정 요구, 그 외 무출력. 항상 exit 0.
#
# 규칙(coding.md §수정 이력 기록 · §주석 규율): 주석은 현재 코드의 사실만 담고,
# 수정 이력(날짜·버전·이전 값·변경 서술)은 code_updates/ 와 git commit 이 담당한다.
#
# 실행: bash coding/tests/comment-gate.test.sh
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="$DIR/../hooks/coding-comment-gate.py"
PY="$(command -v python3 || command -v python)"
[ -n "$PY" ] || { echo "python3 없음"; exit 2; }

PASS=0
FAIL=0
FIX=""
OUT=""

setup() {
  FIX="$(mktemp -d)"; OUT="$FIX/.stdout"
  mkdir -p "$FIX/docs/claude_guideline/coding" "$FIX/src" "$FIX/docs/code_updates"
  echo "# coding 규칙" > "$FIX/docs/claude_guideline/coding/coding.md"
}
teardown() { [ -n "$FIX" ] && rm -rf "$FIX"; }

# edit <상대경로> <new_string>
edit() {
  "$PY" - "$1" "$2" "$FIX" <<'PYEOF' | "$PY" "$HOOK" >"$OUT" 2>&1
import json,sys
rel,new,fix=sys.argv[1],sys.argv[2],sys.argv[3]
print(json.dumps({"tool_name":"Edit","cwd":fix,
    "tool_input":{"file_path":fix+"/"+rel,"new_string":new}},ensure_ascii=False))
PYEOF
  RC=$?
}

blocked() {  # blocked <이름> <기대: yes|no>
  local got; got=$(grep -c '"decision": *"block"' "$OUT" 2>/dev/null)
  local act; [ "${got:-0}" -gt 0 ] && act=yes || act=no
  if [ "$act" = "$2" ]; then printf '  ✓ %s\n' "$1"; PASS=$((PASS+1))
  else printf '  ✗ %s — 기대 %s, 실제 %s. 출력:\n%s\n' "$1" "$2" "$act" "$(sed 's/^/      /' "$OUT")"; FAIL=$((FAIL+1)); fi
}
has() {
  if grep -qF -- "$2" "$OUT" 2>/dev/null; then printf '  ✓ %s\n' "$1"; PASS=$((PASS+1))
  else printf '  ✗ %s — "%s" 없음\n' "$1" "$2"; FAIL=$((FAIL+1)); fi
}

echo "C1  날짜가 든 주석 → 차단"
setup; edit "src/a.py" "# 2026-08-09 계수 조정
def f(): pass"
blocked "차단" yes; has "사유에 규칙 인용" "code_updates"; teardown

echo "C2  값 변천 화살표 → 차단"
setup; edit "src/a.c" "// tol 100 -> 200 으로 늘림
int f(void){return 0;}"
blocked "차단" yes; teardown

echo "C3  버전 태그 → 차단"
setup; edit "src/a.py" "# v2: 재시도 로직 추가
def f(): pass"
blocked "차단" yes; teardown

echo "C4  이력 서술어 → 차단"
setup; edit "src/a.py" "# 이전 값은 0 이었음
X = 1"
blocked "차단" yes; teardown

echo "C5  정상 주석(단위·근거·의도) → 통과"
setup; edit "src/a.py" "# 조향 허용 폭 [counts] — 마스터 캡처 실측 대역
TOL = 200"
blocked "통과" no; teardown

echo "C6  C 블록주석 연속줄의 이력 → 차단 (' * ' 는 진짜 주석 마커)"
setup; edit "src/a.c" "/*
 * 2026-08-09 파라미터 변경함
 */
int f(void){return 0;}"
blocked "차단" yes; teardown

echo "C7  문자열 속 마크다운 굵게는 주석 마커가 아니다 (실측 오탐 고정)"
setup; edit "src/a.sh" 'echo "표는 안 고침 -> **여전히 차단** (기존 훅의 구멍)"'
blocked "통과" no; teardown

echo "C8  비코드 파일(.md) → 통과"
setup; edit "docs/note.md" "# 2026-08-09 변경함"
blocked "통과" no; teardown

echo "C9  code_updates/ 경로 → 통과 (이력의 정당한 배출구)"
setup; edit "docs/code_updates/2026-08-09.md" "# 2026-08-09 변경함"
blocked "통과" no; teardown

echo "C10 TODO(YYYY-MM-DD) 화이트리스트 → 통과"
setup; edit "src/a.py" "# TODO(2026-09-01): 캘리브레이션 재측정
X = 1"
blocked "통과" no; teardown

echo "C11 규칙 비활성(coding.md 부재) → 통과"
setup; rm -rf "$FIX/docs/claude_guideline"
edit "src/a.py" "# 2026-08-09 변경함
X = 1"
blocked "통과" no; teardown

echo "C12 Write/MultiEdit 도 대상"
setup
"$PY" - "$FIX" <<'PYEOF' | "$PY" "$HOOK" >"$OUT" 2>&1
import json,sys
fix=sys.argv[1]
print(json.dumps({"tool_name":"MultiEdit","cwd":fix,"tool_input":{
  "file_path":fix+"/src/a.py",
  "edits":[{"new_string":"X = 1"},{"new_string":"# 2026-08-09 수정함"}]}},ensure_ascii=False))
PYEOF
blocked "차단" yes; teardown

echo "C13 잘못된 stdin → 통과 (훅 결함이 작업을 막지 않는다)"
setup; printf '' | "$PY" "$HOOK" >"$OUT" 2>&1; RC=$?
blocked "통과" no
if [ "$RC" = "0" ]; then printf '  ✓ exit 0\n'; PASS=$((PASS+1))
else printf '  ✗ exit 0 — 실제 %s\n' "$RC"; FAIL=$((FAIL+1)); fi
teardown

echo "C14 «종전» 대비 → 차단"
setup; edit "src/a.py" "# 종전 기본값 10° 대신 5° 를 쓴다
X = 5"
blocked "차단" yes; teardown

echo "C15 과거형 사건 서술 → 차단"
setup; edit "src/a.cpp" "// 이 가드는 2호기 배선에서 빠져 있었다
int f() { return 0; }"
blocked "차단" yes; teardown

echo "C16 리뷰 번호 → 차단"
setup; edit "src/a.py" "# 같은 포트 연속 발사 방지(독립 리뷰 MEDIUM-3)
X = 1"
blocked "차단" yes; teardown

echo "C17 참조형 개정 번호 → 차단"
setup; edit "src/a.cpp" "// 다음 스텝 경계에서 보류한다(ADR-032 결정 18 개정 2)
int f() { return 0; }"
blocked "차단" yes; teardown

echo "C18 연도 없는 날짜·시각 → 차단"
setup; edit "src/a.py" "# 3호기 10-11 00:04 와이어 실측
X = 1"
blocked "차단" yes; teardown

echo "C19 경로 속 날짜는 이름이다 → 통과"
setup; edit "src/a.py" "# 근거: docs/code_updates/2026-09-03_await_acs_response_before_acting.md D3
X = 1"
blocked "통과" no; teardown

echo "C20 낱말 속 «였다» → 통과"
setup; edit "src/a.cpp" "// 깎였다는 사실은 반드시 드러낸다
int f() { return 0; }"
blocked "통과" no; teardown

echo "C21 셸 case 종결자 뒤 문자열은 주석이 아니다 → 통과"
setup; edit "src/a.sh" 'case "$m" in opened) ;; *) say "창이 이미 열려 있었다" ;; esac'
blocked "통과" no; teardown

echo "C22 등급 낱말만 있는 주석 → 통과"
setup; edit "src/a.py" "# 등급이 HIGH 이면 즉시 정지한다
X = 1"
blocked "통과" no; teardown

# 판정 표 — 한 줄 주석씩 넣어 차단 여부를 본다(이름 · 기대 · 줄)
case_line() {
  setup; edit "$1" "$4
X = 1"; blocked "$2" "$3"; teardown
}

echo "C23 날짜 경로 옆의 이력은 여전히 차단 (경로 토큰만 지우고 나머지는 본다)"
case_line src/a.py "경로 + «종전»" yes "# 근거 docs/code_updates/2026-09-03_x.md — 종전 값 10"
case_line src/a.py "경로 + 리뷰 번호" yes "# docs/adr/2026-10-04-estop.md (리뷰 HIGH-2/3 반영)"
case_line src/a.py "날짜 없는 경로 옆 «기존»" yes "# 기존/신규 분기"

echo "C24 마커에 붙은 날짜·이력, 슬래시 날짜 → 차단"
case_line src/a.cpp "//날짜" yes "//2026-08-09 계수 조정"
case_line src/a.cpp "/*날짜" yes "/*2026-08-09 파라미터*/"
case_line src/a.py "슬래시 날짜" yes "# 2026/08/09 계수 변경"
case_line src/a.cpp "//기존" yes "//기존 값 10 을 버린다"
case_line src/a.cpp "//연도 없는 날짜·시각" yes "//10-11 00:04 실측"

echo "C25 단위·식별자 자리 지움이 화살표를 이어 붙이지 않는다 → 통과"
case_line src/a.py "mm/s 화살표" no "# 50 mm/s → 0x606C 1178 (변환식)"
case_line src/a.py "경로 없는 파일명 날짜" no "# 근거 2026-07-23-modbus-fix-proposals.md §1"
case_line src/a.py "지운 날짜 경로 양옆 숫자·화살표" no "# 단계 5 docs/x_2026-01-01.md → 7 순서"

echo "C26 날짜·시각 경계"
case_line src/a.py "버전 문자열" no "# 버전 1.2-3 4:56 호환"
case_line src/a.py "슬래시 월/일 시각" yes "# 8/17 22:40 로그"
case_line src/a.py "시 범위 밖" no "# 범위 10-20 30:40"

echo "C27 리뷰 번호 분기"
case_line src/a.cpp "등급-번호 단독" yes "// HIGH-2 회귀 방지"
case_line src/a.py "두 자리 번호" yes "# MEDIUM-12 회귀 방지"
case_line src/a.py "«리뷰» 접두 문자번호" yes "# 같은 칸 재송(리뷰 L1)"
case_line src/a.cpp "전자 용어 HIGH-Z" no "// 핀을 HIGH-Z 로 둔다"
case_line src/a.cpp "식별자 속 등급" no "// idx = PRIO_HIGH-1 슬롯"

echo "C28 «종전»·«개정» 경계"
case_line src/a.py "최종전압" no "# 최종전압 4.2 V"
case_line src/a.py "외부 문서 개정 2.1" no "# Roboteq 매뉴얼 개정 2.1 §7.3"
case_line src/a.py "미개정" no "# 미개정 1건"
case_line src/a.py "재개정" yes "# 보류(ADR-032 결정 18 재개정 2)"
case_line src/a.py "문장 끝 마침표" yes "# 보류한다(ADR-017 개정 13."

echo "C29 과거형 어미 11종 → 차단"
for w in 였다 이었다 있었다 했었다 바꿨다 고쳤다 되돌렸다 변경했다 수정했다 추가했다 삭제했다; do
  case_line src/a.py "«$w»" yes "# 이 경로는 그때 $w"
done

echo "C30 차단 사유에 패턴별 고치는 법"
setup; edit "src/a.py" "# 보류(ADR-032 결정 18 개정 2)
X = 1"
blocked "차단" yes; has "개정 번호 고치는 법" "결정 번호·절"; teardown

echo "C31 긴 입력도 빨리 끝난다 (경로 토큰 정규식 왼쪽 경계)"
T0=$(date +%s%N)
"$PY" - "$HOOK" <<'PYEOF'
import importlib.util,sys
s=importlib.util.spec_from_file_location("g",sys.argv[1]);g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
g.scan("# " + "a/" * 16000)
g.scan("# " + "a" * 32000)   # 일치가 실패하는 긴 낱말 — 경계가 없으면 시작 위치마다 끝까지 다시 훑는다
PYEOF
MS=$(( ($(date +%s%N) - T0) / 1000000 ))
if [ "$MS" -lt 2000 ]; then printf '  ✓ 32k자 %d ms\n' "$MS"; PASS=$((PASS+1))
else printf '  ✗ 32k자 %d ms — 2000 ms 이상\n' "$MS"; FAIL=$((FAIL+1)); fi

echo
if [ "$FAIL" -eq 0 ]; then echo "✓ 전체 통과 ($PASS)"; exit 0
else echo "✗ 실패 $FAIL / 통과 $PASS"; exit 1; fi
