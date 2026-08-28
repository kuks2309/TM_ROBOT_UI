#!/usr/bin/env bash
# reminder-inject.test.sh — coding-reminder.py 계약 테스트.
#
# 훅 계약(Claude Code UserPromptSubmit): stdin JSON → stdout 이 컨텍스트로 주입, 항상 exit 0.
#
# 2층(계획 전 주입)의 목적: 프롬프트에 등장한 심볼의 **함수표 행을 미리 보여준다**.
# 1층(절차 문구 주입)은 실사격에서 등록·가동 중이었는데도 뚫렸다 — 넣는 것이 "함수표를
# 읽어라"라는 절차이지 "halt_steer 는 목표를 덮어쓴다"라는 내용이 아니었기 때문.
# 3·4층(수정 직전 차단)보다 이르게, 계획을 세우기 전에 사실을 들이민다.
#
# 실행: bash coding/tests/reminder-inject.test.sh
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="$DIR/../hooks/coding-reminder.py"
PY="$(command -v python3 || command -v python)"
[ -n "$PY" ] || { echo "python3 없음"; exit 2; }

PASS=0
FAIL=0
FIX=""
OUTF=""

setup() {
  FIX="$(mktemp -d)"
  OUTF="$FIX/.stdout"
  mkdir -p "$FIX/docs/claude_guideline/coding"
  echo "# coding 규칙" > "$FIX/docs/claude_guideline/coding/coding.md"

  mkdir -p "$FIX/src/Comm/CAN/can_relay/can_relay"
  mkdir -p "$FIX/src/Comm/CAN/can_relay/docs/code_review/can_relay_ros2"
  cat > "$FIX/src/Comm/CAN/can_relay/docs/code_review/can_relay_ros2/2026-08-03.md" <<'EOF'
# can_relay_ros2 코드 리뷰

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 45 | `NodeState` | 6필드 | 인스턴스 | 노드 피드백 상태 | backend.py:33-48 |
| 105 | `RelayBackend.halt_steer` | `reason` | `bool` | 조향축 **실제 정지** — 현재 실측 위치를 새 목표로 덮어쓴다 | backend.py:315-349 |
| 115 | `RelayBackend.halt_note` | — | `str` | 직전 `halt_steer` 가 못 잡은 사유 | backend.py:744-747 |
EOF
  echo "def halt_steer(reason): pass" > "$FIX/src/Comm/CAN/can_relay/can_relay/backend.py"

  # 규칙 문서(인벤토리 아님) — 여기서 뽑아오면 안 된다
  mkdir -p "$FIX/docs/claude_guideline/code_review"
  echo '| 1 | `halt_steer` | 규칙 문서의 예시일 뿐 | review.py:1 |' \
    > "$FIX/docs/claude_guideline/code_review/review.md"
}

teardown() { [ -n "$FIX" ] && rm -rf "$FIX"; }

ask() {  # ask <프롬프트>
  printf '{"prompt":"%s","cwd":"%s","session_id":"sess-A"}' "$1" "$FIX" \
    | "$PY" "$HOOK" >"$OUTF" 2>&1
  RC=$?
}

has() {
  if grep -qF -- "$2" "$OUTF" 2>/dev/null; then
    printf '  ✓ %s\n' "$1"; PASS=$((PASS + 1))
  else
    printf '  ✗ %s — "%s" 없음. 실제:\n%s\n' "$1" "$2" "$(sed 's/^/      /' "$OUTF")"
    FAIL=$((FAIL + 1))
  fi
}

hasnt() {
  if grep -qF -- "$2" "$OUTF" 2>/dev/null; then
    printf '  ✗ %s — "%s" 가 들어있음:\n%s\n' "$1" "$2" "$(sed 's/^/      /' "$OUTF")"
    FAIL=$((FAIL + 1))
  else
    printf '  ✓ %s\n' "$1"; PASS=$((PASS + 1))
  fi
}

check() {
  if [ "$2" = "$3" ]; then printf '  ✓ %s\n' "$1"; PASS=$((PASS + 1))
  else printf '  ✗ %s — 기대 %s, 실제 %s\n' "$1" "$2" "$3"; FAIL=$((FAIL + 1)); fi
}

echo "R1  프롬프트의 심볼이 표에 있으면 그 행을 주입 (계획 전 대면)"
setup
ask "halt_steer 에 제한을 넣도록 코드 수정 해주세요"
check "exit 0" 0 "$RC"
has "기존 SOP 문구 유지" "CODING SOP"
has "halt_steer 행의 기능 문구" "현재 실측 위치를 새 목표로 덮어쓴다"
has "출처 표 경로 표시" "src/Comm/CAN/can_relay/docs/code_review/can_relay_ros2/2026-08-03.md"
has "연관 행도 포함" '가 못 잡은 사유'   # 백틱은 bash 명령치환이라 단언 문자열에서 제외
hasnt "claude_guideline 규칙 문서에서 뽑지 않음" "규칙 문서의 예시일 뿐"
teardown

echo "R2  트리거는 있으나 프롬프트에 심볼 없음 → SOP 만, 행 주입 없음"
setup
ask "코드 수정 해주세요"
check "exit 0" 0 "$RC"
has "SOP 는 주입" "CODING SOP"
hasnt "행 섹션 없음" "함수표 항목"
teardown

echo "R3  표에 없는 심볼 → 행 주입 없음 (없는 걸 지어내지 않음)"
setup
ask "quantum_flux_capacitor 함수를 구현 해주세요"
check "exit 0" 0 "$RC"
has "SOP 는 주입" "CODING SOP"
hasnt "행 섹션 없음" "함수표 항목"
teardown

echo "R4  코딩 트리거 없는 프롬프트 → 아무것도 주입 안 함"
setup
ask "오늘 날씨 어때"
check "exit 0" 0 "$RC"
check "출력 없음" "0" "$(wc -c <"$OUTF" | tr -d ' ')"
teardown

echo "R5  규칙 비활성(coding.md 부재) → 아무것도 주입 안 함"
setup
rm -rf "$FIX/docs/claude_guideline"
ask "halt_steer 코드 수정 해주세요"
check "exit 0" 0 "$RC"
check "출력 없음" "0" "$(wc -c <"$OUTF" | tr -d ' ')"
teardown

echo
if [ "$FAIL" -eq 0 ]; then
  echo "✓ 전체 통과 ($PASS)"; exit 0
else
  echo "✗ 실패 $FAIL / 통과 $PASS"; exit 1
fi
