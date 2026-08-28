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

echo
if [ "$FAIL" -eq 0 ]; then echo "✓ 전체 통과 ($PASS)"; exit 0
else echo "✗ 실패 $FAIL / 통과 $PASS"; exit 1; fi
