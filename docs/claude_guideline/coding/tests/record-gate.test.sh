#!/usr/bin/env bash
# record-gate.test.sh — coding-record-gate.py 계약 테스트.
#
# 훅 계약(Claude Code Stop): stdin JSON(transcript_path·stop_hook_active) →
#   stderr + exit 2 = 종료 차단(모델이 스스로 점검·보완 후 다시 마침), 그 외 exit 0.
#
# 담당 범위: §2(선독)는 PreToolUse 게이트가, §6(표 갱신)은 본 훅이 맡는다.
# ⟦CI:index-fresh⟧ 는 커밋 시점 검사라 커밋하지 않는 턴에서는 표 갱신이 강제되지
# 않는다 — 그 구간을 Stop 시점 대면으로 메운다(판단은 모델, 대면은 강제).
#
# 실행: bash coding/tests/record-gate.test.sh
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="$DIR/../hooks/coding-record-gate.py"
PY="$(command -v python3 || command -v python)"
[ -n "$PY" ] || { echo "python3 없음"; exit 2; }

PASS=0
FAIL=0
FIX=""
ERRF=""
TR=""

setup() {
  FIX="$(mktemp -d)"; ERRF="$FIX/.stderr"; TR="$FIX/transcript.jsonl"
  mkdir -p "$FIX/docs/claude_guideline/coding"
  echo "# coding 규칙" > "$FIX/docs/claude_guideline/coding/coding.md"

  mkdir -p "$FIX/src/can_relay/can_relay" "$FIX/src/can_relay/docs/code_review/can_relay_ros2"
  cat > "$FIX/src/can_relay/docs/code_review/can_relay_ros2/2026-08-03.md" <<'EOF'
| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 105 | `RelayBackend.halt_steer` | `reason` | `bool` | 조향축 실제 정지 | backend.py:315-349 |
EOF
  echo "def halt_steer(r): pass" > "$FIX/src/can_relay/can_relay/backend.py"
  echo "def untabled(): pass"    > "$FIX/src/can_relay/can_relay/helper.py"
  mkdir -p "$FIX/docs/code_updates"; echo "# 이력" > "$FIX/docs/code_updates/2026-08-09.md"
  echo "# readme" > "$FIX/README.md"
  git -C "$FIX" init -q
}
teardown() { [ -n "$FIX" ] && rm -rf "$FIX"; }

# transcript 작성: 사용자 텍스트 1건 뒤에 tool_use 들을 쌓는다.
# tr_add <tool> <repo상대경로>
tr_reset() { printf '{"type":"user","message":{"content":"작업해줘"}}\n' > "$TR"; }
tr_add() {
  "$PY" - "$TR" "$1" "$FIX/$2" <<'PYEOF'
import json,sys
tr,tool,path=sys.argv[1],sys.argv[2],sys.argv[3]
with open(tr,"a",encoding="utf-8") as f:
    f.write(json.dumps({"type":"assistant","message":{"content":[
        {"type":"tool_use","id":"t%d" % (abs(hash(path+tool)) % 9999),"name":tool,
         "input":{"file_path":path}}]}},ensure_ascii=False)+"\n")
PYEOF
}

stop() {  # stop [stop_hook_active]
  printf '{"transcript_path":"%s","cwd":"%s","session_id":"sess-A","stop_hook_active":%s}' \
    "$TR" "$FIX" "${1:-false}" | "$PY" "$HOOK" >/dev/null 2>"$ERRF"
  RC=$?
  grep -qE "SyntaxError|Traceback|can't open file" "$ERRF" 2>/dev/null && RC="ERROR(훅 실행 실패)"
}

check() { if [ "$2" = "$3" ]; then printf '  ✓ %s\n' "$1"; PASS=$((PASS+1));
          else printf '  ✗ %s — 기대 %s, 실제 %s\n' "$1" "$2" "$3"; FAIL=$((FAIL+1)); fi; }
has()   { if grep -qF -- "$2" "$ERRF" 2>/dev/null; then printf '  ✓ %s\n' "$1"; PASS=$((PASS+1));
          else printf '  ✗ %s — "%s" 없음. 실제:\n%s\n' "$1" "$2" "$(sed 's/^/      /' "$ERRF")"; FAIL=$((FAIL+1)); fi; }
hasnt() { if grep -qF -- "$2" "$ERRF" 2>/dev/null; then printf '  ✗ %s — "%s" 있음\n' "$1" "$2"; FAIL=$((FAIL+1));
          else printf '  ✓ %s\n' "$1"; PASS=$((PASS+1)); fi; }

echo "S1  코드 수정 + 표 미수정 → 차단"
setup; tr_reset
tr_add Edit "src/can_relay/can_relay/backend.py"
stop
check "exit 2 (차단)" 2 "$RC"
has "수정한 코드 파일 명시" "backend.py"
has "갱신할 표 명시" "can_relay_ros2/2026-08-03.md"
has "내부 로직만이면 그대로 마치라는 예외 안내" "내부 로직"
teardown

echo "S2  표 갱신 + 이력 기록 둘 다 → 통과 (§6 은 둘을 모두 요구)"
setup; tr_reset
tr_add Edit "src/can_relay/can_relay/backend.py"
tr_add Edit "src/can_relay/docs/code_review/can_relay_ros2/2026-08-03.md"
tr_add Write "docs/code_updates/2026-08-09.md"
stop
check "exit 0 (통과)" 0 "$RC"
teardown

echo "S2b 표만 갱신하고 이력 미기록 → 차단"
setup; tr_reset
tr_add Edit "src/can_relay/can_relay/backend.py"
tr_add Edit "src/can_relay/docs/code_review/can_relay_ros2/2026-08-03.md"
stop
check "exit 2 (차단)" 2 "$RC"
has "이력 기록을 요구" "code_updates"
hasnt "표는 이미 갱신했으므로 표 요구는 없음" "함수표를 갱신하지"
teardown

echo "S3  code_updates 만 쓰고 표는 안 고침 → 차단 (이력 기록이 표 갱신을 대신하지 않는다)"
setup; tr_reset
tr_add Edit "src/can_relay/can_relay/backend.py"
tr_add Write "docs/code_updates/2026-08-09.md"
stop
check "exit 2 (차단)" 2 "$RC"
teardown

echo "S4  코드 수정 없음 → 통과"
setup; tr_reset
tr_add Edit "README.md"
stop
check "exit 0 (통과)" 0 "$RC"
teardown

echo "S5  stop_hook_active → 통과 (검토 루프 1패스 제한)"
setup; tr_reset
tr_add Edit "src/can_relay/can_relay/backend.py"
stop true
check "exit 0 (통과)" 0 "$RC"
teardown

echo "S6  규칙 비활성(coding.md 부재) → 통과"
setup; rm -rf "$FIX/docs/claude_guideline"; tr_reset
tr_add Edit "src/can_relay/can_relay/backend.py"
stop
check "exit 0 (통과)" 0 "$RC"
teardown

echo "S7  표가 없는 파일 → 표 요구는 안 하되(게이트 소관) 이력은 요구"
setup; tr_reset
tr_add Edit "src/can_relay/can_relay/helper.py"
stop
check "exit 2 (차단)" 2 "$RC"
has "이력 기록 요구" "code_updates"
hasnt "표 요구는 없음 (이중 경보 금지)" "함수표를 갱신하지"
teardown

echo "S7b 표 없는 파일 + 이력 기록 → 표 부재 대면 (구 침묵 계약 폐기 — 2026-08-23 실측: 표 없는 구역이 무기한 무강제)"
setup; tr_reset
tr_add Edit "src/can_relay/can_relay/helper.py"
tr_add Write "docs/code_updates/2026-08-09.md"
stop
check "exit 2 (표 부재 대면)" 2 "$RC"
has "표 부재 안내" "커버하는 함수표가 없는"
hasnt "갱신 경보는 없음 (표가 없으므로)" "함수표를 갱신하지"
teardown

echo "S8  표 파일 자체만 수정 → 통과 (코드 수정 아님)"
setup; tr_reset
tr_add Edit "src/can_relay/docs/code_review/can_relay_ros2/2026-08-03.md"
stop
check "exit 0 (통과)" 0 "$RC"
teardown

echo "S9  transcript 없음/깨짐 → 통과 (훅 결함이 작업을 막지 않는다)"
setup
printf '{"transcript_path":"/nonexistent","cwd":"%s","session_id":"s","stop_hook_active":false}' "$FIX" \
  | "$PY" "$HOOK" >/dev/null 2>"$ERRF"; RC=$?
check "exit 0" 0 "$RC"
teardown

# tr_add_bash <command> — Bash tool_use 를 transcript 에 추가 (G3: Bash 쓰기 우회 검출)
tr_add_bash() {
  "$PY" - "$TR" "$1" <<'PYEOF'
import json,sys
tr,cmd=sys.argv[1],sys.argv[2]
with open(tr,"a",encoding="utf-8") as f:
    f.write(json.dumps({"type":"assistant","message":{"content":[
        {"type":"tool_use","id":"b%d" % (abs(hash(cmd)) % 9999),"name":"Bash",
         "input":{"command":cmd}}]}},ensure_ascii=False)+"\n")
PYEOF
}

echo "S10 docs/ 직속 함수표 연결 — 표 미갱신 코드 수정 → 갱신 경보 (2026-08-23 이원화 봉합)"
setup; tr_reset
mkdir -p "$FIX/src/can_relay/docs"
printf '| 1 | untabled | - | - | 헬퍼 | helper.py:1-1 |\n' > "$FIX/src/can_relay/docs/function_table.md"
tr_add Edit "src/can_relay/can_relay/helper.py"
tr_add Write "docs/code_updates/2026-08-09.md"
stop
check "exit 2 (docs 직속 표가 커버 표로 인정됨)" 2 "$RC"
has "갱신 경보" "함수표를 갱신하지"
has "docs 직속 표 경로 노출" "function_table.md"
teardown

echo "S11 Bash 리다이렉션으로 쓴 표 없는 코드 → 표 부재 대면 (선독 게이트 우회 회수)"
setup; tr_reset
echo "x=1" > "$FIX/src/can_relay/can_relay/bashmade.py"
tr_add_bash "echo 'x=2' > src/can_relay/can_relay/bashmade.py"
stop
check "exit 2 (Bash 쓰기 검출)" 2 "$RC"
has "표 부재 안내" "커버하는 함수표가 없는"
teardown

echo "S12 Bash sed -i 로 고친 커버 코드 → 갱신 경보"
setup; tr_reset
tr_add_bash "sed -i 's/pass/return 1/' src/can_relay/can_relay/backend.py"
stop
check "exit 2" 2 "$RC"
has "갱신 경보" "함수표를 갱신하지"
teardown

echo "S13 설계본 표(앵커 없는 파일명 등재)도 커버로 인정 — 코드 0줄 단계 표의 영구 미연결 방지"
setup; tr_reset
mkdir -p "$FIX/src/can_relay/docs"
printf '# 설계본 (코드 0줄)\n| 1 | planned_fn | - | - | 계획 함수 | helper.py |\n' > "$FIX/src/can_relay/docs/function_table.md"
tr_add Edit "src/can_relay/can_relay/helper.py"
tr_add Write "docs/code_updates/2026-08-09.md"
stop
check "exit 2 (설계본 표가 커버)" 2 "$RC"
has "갱신 경보 (표 부재 아님)" "함수표를 갱신하지"
hasnt "표 부재 안내는 없음" "커버하는 함수표가 없는"
teardown

echo
if [ "$FAIL" -eq 0 ]; then echo "✓ 전체 통과 ($PASS)"; exit 0
else echo "✗ 실패 $FAIL / 통과 $PASS"; exit 1; fi
