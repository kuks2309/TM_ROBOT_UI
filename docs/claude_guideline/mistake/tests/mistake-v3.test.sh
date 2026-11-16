#!/usr/bin/env bash
# mistake-v3.test.sh — mistake 번들 v3 계약 테스트.
#
# 계약의 축은 **관련성**이다. v2 는 저장소의 모든 미해결 사건으로 모든 코드 수정을
# 막았고(차단이 커짐), 닫힌 사건은 아예 읽히지 않았다(처방이 사장됨). v3 는 그 파일에
# 걸린 사건만 보고, open 이면 차단·closed 면 안내한다.
#
# 음성 대조를 함께 잡는다 — 걸리지 말아야 할 때 침묵하는지. 통과만 확인하는 단언은
# 죽은 단언과 구분되지 않는다.
#
# 실행: bash mistake/tests/mistake-v3.test.sh
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
B="$DIR/.."
PY="$(command -v python3 || command -v python)"
[ -n "$PY" ] || { echo "python3 없음"; exit 2; }

PASS=0; FAIL=0; FIX=""; OUT=""; RC=0

setup() {
  FIX="$(mktemp -d)"; OUT="$FIX/.out"
  mkdir -p "$FIX/docs/claude_guideline/mistake" "$FIX/docs/claude-mistake" "$FIX/src"
  echo "# mistake 규칙" > "$FIX/docs/claude_guideline/mistake/mistake.md"
}
teardown() { [ -n "$FIX" ] && rm -rf "$FIX"; }

# entry <id> <kind> <detector> <status> <본문>
entry() {
  { printf -- '---\nid: %s\nkind: %s\ndetector: %s\nstatus: %s\n---\n\n' "$1" "$2" "$3" "$4"
    printf '# %s 12:00 (KST) — 시험 사건\n\n' "$1"
    printf '## 무엇을 했는가\n%s\n\n' "$5"
    printf '## 무엇이 잘못이었나\n규칙 인용\n\n## 원인 분석\n분석\n\n## 재발 방지\n처방 본문\n'
  } > "$FIX/docs/claude-mistake/$1.md"
}

edit() {  # edit <상대경로> [session]
  printf '{"hook_event_name":"PreToolUse","tool_name":"Edit","tool_input":{"file_path":"%s/%s"},"cwd":"%s","session_id":"%s"}' \
    "$FIX" "$1" "$FIX" "${2:-s1}" | "$PY" "$B/hooks/mistake-relevance.py" > "$OUT" 2>&1
  RC=$?
}
has()   { if grep -qF -- "$2" "$OUT" 2>/dev/null; then printf '  ✓ %s\n' "$1"; PASS=$((PASS+1));
          else printf '  ✗ %s — "%s" 없음. 실제:\n%s\n' "$1" "$2" "$(sed 's/^/      /' "$OUT")"; FAIL=$((FAIL+1)); fi; }
hasnt() { if grep -qF -- "$2" "$OUT" 2>/dev/null; then printf '  ✗ %s — "%s" 있음:\n%s\n' "$1" "$2" "$(sed 's/^/      /' "$OUT")"; FAIL=$((FAIL+1));
          else printf '  ✓ %s\n' "$1"; PASS=$((PASS+1)); fi; }
empty() { if [ ! -s "$OUT" ]; then printf '  ✓ %s\n' "$1"; PASS=$((PASS+1));
          else printf '  ✗ %s — 출력 있음:\n%s\n' "$1" "$(sed 's/^/      /' "$OUT")"; FAIL=$((FAIL+1)); fi; }
check() { if [ "$2" = "$3" ]; then printf '  ✓ %s\n' "$1"; PASS=$((PASS+1));
          else printf '  ✗ %s — 기대 %s, 실제 %s\n' "$1" "$2" "$3"; FAIL=$((FAIL+1)); fi; }

echo "M1  닫힌 사건 — 그 파일을 고치면 처방을 안내(차단 아님)"
setup
echo "def run(): pass" > "$FIX/src/dock.py"
entry 2026-01-01-001 B "none (사유)" closed 'src/dock.py 를 고쳤다'
edit src/dock.py
has   "안내 발화"        "이 파일에 걸린 과거 사건"
has   "사건 지목"        "2026-01-01-001"
has   "처방 전달"        "재발 방지: 처방 본문"
hasnt "차단 아님"        "\"deny\""
teardown

echo "M2  미해결 사건 — 그 파일을 고치면 차단"
setup
echo "def run(): pass" > "$FIX/src/dock.py"
entry 2026-01-01-002 B "none (사유)" open 'src/dock.py 를 고쳤다'
edit src/dock.py
has "차단"        "deny"
has "미해결 표시" "미해결"
teardown

echo "M3  무관한 파일 — 침묵 (음성 대조: v2 는 여기서도 막았다)"
setup
echo "def other(): pass" > "$FIX/src/unrelated.py"
entry 2026-01-01-003 B "none (사유)" open 'src/dock.py 를 고쳤다'
edit src/unrelated.py
empty "무관한 미해결 사건으로는 막지 않는다"
teardown

echo "M4  키워드 전파 — 토큰 2개 이상이면 걸리고, 1개면 침묵"
setup
printf 'import subprocess\nsubprocess.run(["pkill","-f","ros2"])\nsetsid_x=1\n' > "$FIX/src/stack_ctl.py"
entry 2026-01-01-004 B "none (사유)" closed '`pkill` 로 자식까지 죽였다. `setsid_x` 래퍼가 고아를 만든다.'
edit src/stack_ctl.py
has "이름 안 적힌 파일도 계열 토큰으로 걸림" "2026-01-01-004"
has "걸린 이유가 토큰임을 밝힘"              "같은 계열 토큰"
teardown
setup
printf 'import subprocess\nsubprocess.run(["pkill","-f","x"])\n' > "$FIX/src/one.py"
entry 2026-01-01-005 B "none (사유)" closed '`pkill` 만 인용된 사건'
edit src/one.py
empty "토큰 1개는 우연 일치로 보고 침묵"
teardown

echo "M10 차단은 강한 근거에서만 — 토큰 일치만이면 미해결이어도 안내"
setup
printf 'import subprocess\nsubprocess.run(["pkill","-f","ros2"])\nsetsid_x=1\n' > "$FIX/src/other.py"
entry 2026-01-01-020 B "none (사유)" open '`pkill` 로 자식까지 죽였다. `setsid_x` 래퍼가 고아를 만든다.'
edit src/other.py
has   "안내는 한다"        "2026-01-01-020"
hasnt "차단하지 않는다"    "deny"
teardown

echo "M11 v2→v3 재판정 대기는 강한 근거여도 차단하지 않는다"
setup
echo "def run(): pass" > "$FIX/src/dock.py"
entry 2026-01-01-021 B "none (사유 미기재 — 검출 가능한지 재판정 필요)" open 'src/dock.py 를 고쳤다'
edit src/dock.py
has   "안내는 한다"        "2026-01-01-021"
hasnt "차단하지 않는다"    "deny"
teardown

echo "M5  세션당 사건 1회 (안내 반복 금지)"
setup
echo "def run(): pass" > "$FIX/src/dock.py"
entry 2026-01-01-006 B "none (사유)" closed 'src/dock.py 를 고쳤다'
edit src/dock.py s9; has "첫 발화" "2026-01-01-006"
edit src/dock.py s9; empty "같은 세션 재발화 없음"
teardown

echo "M6  우회 스위치·비대상 (음성 대조)"
setup
echo "x" > "$FIX/README.md"
entry 2026-01-01-007 B "none (사유)" open 'README.md 를 고쳤다'
edit README.md; empty "코드 파일이 아니면 대상 아님"
teardown
setup
echo "def run(): pass" > "$FIX/src/dock.py"
entry 2026-01-01-008 B "none (사유)" open 'src/dock.py 를 고쳤다'
MISTAKE_RELEVANCE_SKIP=1 edit src/dock.py; empty "우회 스위치"
teardown

echo "M7  entry-lint — closure 는 기계 조건"
setup
entry 2026-01-01-009 A "detectors/2026-01-01-009.sh" closed '검출자 없는 A'
bash "$B/checks/entry-lint.sh" "$FIX/docs/claude-mistake" > "$OUT" 2>&1; check "A인데 검출자 없음 → 실패" 1 "$?"
has "사유 표시" "검출자 파일 없음"
teardown
setup
entry 2026-01-01-010 B "none (사유 있음)" closed '백틱 없는 본문'
bash "$B/checks/entry-lint.sh" "$FIX/docs/claude-mistake" > "$OUT" 2>&1; check "B closed 인데 걸림 조건 없음 → 실패" 1 "$?"
has "사유 표시" "코드 토픽 인용 2개 미만"
teardown
setup
entry 2026-01-01-011 B "none" closed '`a` 와 `b`'
bash "$B/checks/entry-lint.sh" "$FIX/docs/claude-mistake" > "$OUT" 2>&1; check "B 인데 불가 사유 없음 → 실패" 1 "$?"
teardown

echo "M8  detectors/run.sh — 죽은 검사를 잡는다"
setup
mkdir -p "$FIX/det/x.fixture/bad"
printf 'exit 0\n' > "$FIX/det/x.sh"                 # 무엇도 잡지 않는 검사
# 표본 문구를 조립해서 쓴다 — 이 테스트 파일 자체가 검출자에 걸리면 안 된다
# (테스트도 코드다. 원 사고가 정확히 테스트에서 났으므로 tests/ 를 스캔에서 빼지 않는다).
DECL='local a'; printf '%s; [ %s -eq 0 ]\n' "$DECL" '$?' > "$FIX/det/x.fixture/bad/y.sh"
cp "$B/detectors/run.sh" "$FIX/det/run.sh"
bash "$FIX/det/run.sh" "$FIX" > "$OUT" 2>&1; check "표본에서 안 걸리는 검사 → 실패" 1 "$?"
has "죽은 검사로 보고" "죽은 검사"
teardown

echo "M9  index-gen — 신선도 검사"
setup
entry 2026-01-01-012 B "none (사유)" closed '`a` 와 `b`'
"$PY" "$B/checks/index-gen.py" "$FIX/docs/claude-mistake" >/dev/null 2>&1
"$PY" "$B/checks/index-gen.py" "$FIX/docs/claude-mistake" --check > "$OUT" 2>&1; check "생성 직후 최신" 0 "$?"
entry 2026-01-01-013 B "none (사유)" closed '`c` 와 `d`'
"$PY" "$B/checks/index-gen.py" "$FIX/docs/claude-mistake" --check > "$OUT" 2>&1; check "사건 추가 후 낡음 검출" 1 "$?"
teardown

echo
if [ "$FAIL" -eq 0 ]; then echo "✓ 전체 통과 ($PASS)"; exit 0
else echo "✗ 실패 $FAIL / 통과 $PASS"; exit 1; fi
