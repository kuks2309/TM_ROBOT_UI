#!/usr/bin/env bash
# inventory-gate.test.sh — coding-inventory-gate.py 계약 테스트.
#
# 훅 계약(Claude Code):
#   PreToolUse  : stdin JSON → exit 2 + stderr = 도구 차단, 그 외 exit 0
#   PostToolUse : stdin JSON → 부수효과(읽은 파일 기록), 항상 exit 0
#
# fixture 는 실사격 저장소(Ford-CATL-AMR/Big-AMR)의 구조를 그대로 본뜬다:
#   - 표의 위치 컬럼은 **파일명:줄** 형식 (`backend.py:315-349`) — 저장소 상대경로가 아님
#   - 표는 모듈 로컬(권위) + 루트 집계로 이중 기록
#   - docs/claude_guideline/ 아래 규칙 문서가 공존 (인벤토리가 아님)
#   - 같은 파일명(backend.py)이 여러 모듈에 존재
# 실패 사례 재현: 표에 "조향축 실제 정지 — 현재 실측 위치를 새 목표로 덮어쓴다" 가
# 적힌 함수를 표를 읽지 않은 채 수정해 용도를 오판.
#
# 실행: bash coding/tests/inventory-gate.test.sh
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="$DIR/../hooks/coding-inventory-gate.py"
PY="$(command -v python3 || command -v python)"
[ -n "$PY" ] || { echo "python3 없음"; exit 2; }

PASS=0
FAIL=0
FIX=""
ERRF=""

# ── fixture ────────────────────────────────────────────────────────────────
setup() {
  FIX="$(mktemp -d)"
  ERRF="$FIX/.stderr"

  # 규칙 활성 마커 + 규칙 문서(인벤토리 아님 — 표 후보에서 제외되어야 함)
  mkdir -p "$FIX/docs/claude_guideline/coding" "$FIX/docs/claude_guideline/code_review"
  echo "# coding 규칙" > "$FIX/docs/claude_guideline/coding/coding.md"
  cat > "$FIX/docs/claude_guideline/code_review/review.md" <<'EOF'
# 코드 리뷰 규칙 (SSOT)
함수 표 컬럼 순서 고정: `#`, `함수`, `입력`, `출력`, `기능`, `위치(file:line)`.
예: setup.py:1 · widget.py:10 처럼 표기한다.
EOF

  # can_relay 모듈 — 모듈 로컬 표(권위)
  mkdir -p "$FIX/src/Comm/CAN/can_relay/can_relay"
  mkdir -p "$FIX/src/Comm/CAN/can_relay/docs/code_review/can_relay_ros2"
  cat > "$FIX/src/Comm/CAN/can_relay/docs/code_review/can_relay_ros2/2026-08-03.md" <<'EOF'
# can_relay_ros2 코드 리뷰

## 3. 함수 리스트 표

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 40 | `NodeState` | 6필드 | 인스턴스 | 노드 피드백 상태 | backend.py:33-48 |
| 41 | `NodeState.fresh` | `now,ttl` | `bool` | 피드백 신선도 | backend.py:47-48 |
| 42 | `RelayConfig` | 13필드 | 인스턴스 | 배선·한계·주기 | backend.py:51-68 |
| 43 | `RelayBackend.__init__` | `link,cfg` | None | 상태·락 초기화 | backend.py:78-101 |
| 44 | `RelayBackend.start` | — | None | 제어 스레드 기동 | backend.py:104-116 |
| 45 | `RelayBackend.shutdown` | — | None | 정지 후 스레드 종료 | backend.py:118-135 |
| 46 | `RelayBackend.set_drive_mmps` | `mmps` | None | 워치독 갱신 | backend.py:138-145 |
| 47 | `RelayBackend.set_steer_deg` | `deg` | `float` | 클램프·호밍 중 거부 | backend.py:147-169 |
| 48 | `RelayBackend.tick` | — | None | 제어 주기 1회 | backend.py:172-260 |
| 49 | `RelayBackend.feedback` | — | `dict` | 최근 피드백 스냅샷 | backend.py:263-280 |
| 60 | `steer` | — | `float` | 미끼 — 부분문자열 매칭이면 halt_steer 안에서 잘못 걸린다 | backend.py:290 |
| 105 | `RelayBackend.halt_steer` | `reason` | `bool` | 조향축 **실제 정지** — 현재 실측 위치를 새 목표로 덮어쓴다 | backend.py:315-349 |
| 106 | `RelayBackend.stop` | — | `bool` | 주행축 정지 | backend.py:352-370 |

산문 줄: 구성요소인 `halt_steer` 에는 시험이 있으나 결합은 미고정이다 · backend.py:999
EOF
  echo "def halt_steer(reason): pass" > "$FIX/src/Comm/CAN/can_relay/can_relay/backend.py"
  echo "def untabled(): pass"        > "$FIX/src/Comm/CAN/can_relay/can_relay/helper.py"

  # 루트 집계 표 — 같은 파일명을 담지만 모듈 로컬이 우선되어야 함
  mkdir -p "$FIX/docs/code_review/can_relay_ros2"
  cat > "$FIX/docs/code_review/can_relay_ros2/2026-08-03.md" <<'EOF'
| # | 함수 | 기능 | 위치(file:line) |
|---|---|---|---|
| 105 | `halt_steer` | (루트 집계본) | backend.py:315-349 |
EOF

  # 다른 모듈에도 같은 이름의 backend.py — 자기 모듈 표만 요구되어야 함
  mkdir -p "$FIX/src/Actuators/motor_control/motor_control"
  mkdir -p "$FIX/src/Actuators/motor_control/docs/code_review/motor_control"
  cat > "$FIX/src/Actuators/motor_control/docs/code_review/motor_control/2026-07-26.md" <<'EOF'
| # | 함수 | 기능 | 위치(file:line) |
|---|---|---|---|
| 12 | `drive` | 모터 구동 | backend.py:44-60 |
EOF
  echo "def drive(): pass" > "$FIX/src/Actuators/motor_control/motor_control/backend.py"

  # 파일명이 산문에만 등장(앵커 없음) — 커버로 보면 안 됨
  mkdir -p "$FIX/src/Misc/notes/docs/code_review/misc" "$FIX/src/Misc/notes/pkg"
  cat > "$FIX/src/Misc/notes/docs/code_review/misc/2026-08-01.md" <<'EOF'
리뷰 메모: 이 패키지의 loader.py 는 다음 회차에 다룬다(표 미작성).
EOF
  echo "def load(): pass" > "$FIX/src/Misc/notes/pkg/loader.py"

  echo "# readme" > "$FIX/README.md"

  git -C "$FIX" init -q
  git -C "$FIX" config user.email t@example.com
  git -C "$FIX" config user.name tester
}

teardown() { [ -n "$FIX" ] && rm -rf "$FIX"; }

BACKEND="src/Comm/CAN/can_relay/can_relay/backend.py"
LOCALTBL="src/Comm/CAN/can_relay/docs/code_review/can_relay_ros2/2026-08-03.md"
ROOTTBL="docs/code_review/can_relay_ros2/2026-08-03.md"
MOTORTBL="src/Actuators/motor_control/docs/code_review/motor_control/2026-07-26.md"

# ── 훅 호출 ────────────────────────────────────────────────────────────────
hook() {  # hook <event> <tool> <repo상대경로> <sid> [수정 payload(old_string)]
  local ev="$1" tool="$2" rel="$3" sid="$4" payload="${5:-}" json
  json=$(printf '{"hook_event_name":"%s","tool_name":"%s","tool_input":{"file_path":"%s","old_string":"%s"},"cwd":"%s","session_id":"%s"}' \
    "$ev" "$tool" "$FIX/$rel" "$payload" "$FIX" "$sid")
  printf '%s' "$json" | "$PY" "$HOOK" >/dev/null 2>"$ERRF"
  RC=$?
  # 인터프리터 오류(파일 없음·SyntaxError)도 exit 2 라 차단 신호와 충돌한다.
  # 훅 계약 위반이므로 별도 코드로 승격해 거짓 통과를 막는다.
  if grep -qE "can't open file|SyntaxError|Traceback" "$ERRF" 2>/dev/null; then
    RC="ERROR(훅 실행 실패)"
  fi
}

check() {  # check <이름> <기대> <실제>
  if [ "$2" = "$3" ]; then
    printf '  ✓ %s\n' "$1"; PASS=$((PASS + 1))
  else
    printf '  ✗ %s — 기대 %s, 실제 %s\n' "$1" "$2" "$3"; FAIL=$((FAIL + 1))
  fi
}

has() {  # has <이름> <문자열>
  if grep -qF -- "$2" "$ERRF" 2>/dev/null; then
    printf '  ✓ %s\n' "$1"; PASS=$((PASS + 1))
  else
    printf '  ✗ %s — "%s" 없음. 실제:\n%s\n' "$1" "$2" "$(sed 's/^/      /' "$ERRF" 2>/dev/null)"
    FAIL=$((FAIL + 1))
  fi
}

hasnt() {  # hasnt <이름> <문자열>
  if grep -qF -- "$2" "$ERRF" 2>/dev/null; then
    printf '  ✗ %s — "%s" 가 들어있음:\n%s\n' "$1" "$2" "$(sed 's/^/      /' "$ERRF")"
    FAIL=$((FAIL + 1))
  else
    printf '  ✓ %s\n' "$1"; PASS=$((PASS + 1))
  fi
}

# ── 테스트 ─────────────────────────────────────────────────────────────────

echo "T1  모듈 로컬 표 있음 + 미독 → 차단"
setup
hook PreToolUse Edit "$BACKEND" sess-A
check "exit 2 (차단)" 2 "$RC"
has "stderr 에 모듈 로컬 표 명시" "$LOCALTBL"
has "stderr 에 대상 파일 명시" "$BACKEND"
teardown

echo "T1b 차단 메시지가 표의 행을 실어 보낸다 (경로만 알려주면 3만 바이트에서 못 찾음)"
setup
hook PreToolUse Edit "$BACKEND" sess-A
has "표 행이 실림" "노드 피드백 상태"
has "잘림을 고지 (감춘 행이 있음을 숨기지 않음)" "외 6 행"
hasnt "타 모듈 동명 파일의 행은 섞이지 않음" "모터 구동"
teardown

echo "T1c 수정 payload 의 심볼이 있는 행을 우선 표시 (앞 8행 자르면 정작 그 행이 묻힘)"
setup
hook PreToolUse Edit "$BACKEND" sess-A "def halt_steer(self, reason):"
has "halt_steer 행의 기능 문구가 표시됨" "현재 실측 위치를 새 목표로 덮어쓴다"
has "행 번호 105 표시" "| 105 |"
teardown

echo "T1d 토큰 매칭은 단어 경계 — `steer` 가 halt_steer 안에서 걸리면 안 됨"
setup
hook PreToolUse Edit "$BACKEND" sess-A "def halt_steer(self, reason):"
hasnt "미끼 행이 상위에 오지 않음" "미끼 — 부분문자열 매칭이면"
teardown

echo "T1e 표 행이 산문 줄보다 먼저 (섹션 제목이 '표 항목'이므로)"
setup
hook PreToolUse Edit "$BACKEND" sess-A "def halt_steer(self, reason):"
FIRST=$(sed -n '/▼ 그 표에 적힌/,$p' "$ERRF" | sed -n '2p')
check "첫 행이 #105 표 행" "yes" "$(printf '%s' "$FIRST" | grep -qF '| 105 |' && echo yes || echo no)"
teardown

echo "T2  Read 기록 → 목록 파일에 상대경로 누적"
setup
hook PostToolUse Read "$LOCALTBL" sess-A
check "exit 0" 0 "$RC"
L="$FIX/.git/coding/reads/sess-A.list"
check "목록 파일 생성" "yes" "$([ -f "$L" ] && echo yes || echo no)"
check "상대경로 기록" "yes" "$(grep -qxF "$LOCALTBL" "$L" 2>/dev/null && echo yes || echo no)"
teardown

echo "T3  모듈 로컬 표 읽음 → 통과"
setup
hook PostToolUse Read "$LOCALTBL" sess-A
hook PreToolUse Edit "$BACKEND" sess-A
check "exit 0 (통과)" 0 "$RC"
teardown

echo "T4  모듈 로컬 우선 — 루트 집계본만 읽으면 여전히 차단"
setup
hook PostToolUse Read "$ROOTTBL" sess-A
hook PreToolUse Edit "$BACKEND" sess-A
check "exit 2 (차단)" 2 "$RC"
teardown

echo "T5  타 모듈 표는 무관 — motor_control 표를 읽어도 can_relay 는 차단"
setup
hook PostToolUse Read "$MOTORTBL" sess-A
hook PreToolUse Edit "$BACKEND" sess-A
check "exit 2 (차단)" 2 "$RC"
hasnt "타 모듈 표를 요구 목록에 넣지 않음" "motor_control"
teardown

echo "T6  앵커 필수 — 파일명이 산문에만 등장하면 커버 아님 (→ 표 작성 요구)"
setup
hook PreToolUse Edit "src/Misc/notes/pkg/loader.py" sess-A
check "exit 2 (차단)" 2 "$RC"
has "'표 없음' 메시지" "함수표가 없습니다"
hasnt "산문만 있는 파일을 표로 지목하지 않음" "misc/2026-08-01.md"
teardown

echo "T7  claude_guideline 규칙 문서는 표 후보 아님 (→ 표 작성 요구)"
setup
rm -rf "$FIX/src/Comm/CAN/can_relay/docs" "$FIX/docs/code_review"
mkdir -p "$FIX/pkg" && echo "x=1" > "$FIX/pkg/setup.py"
hook PreToolUse Edit "pkg/setup.py" sess-A
check "exit 2 (차단)" 2 "$RC"
has "'표 없음' 메시지" "함수표가 없습니다"
hasnt "규칙 문서를 표로 지목하지 않음" "claude_guideline/code_review/review.md"
teardown

echo "T8  세션 격리 — 타 세션이 읽어도 내 세션은 차단"
setup
hook PostToolUse Read "$LOCALTBL" sess-OTHER
hook PreToolUse Edit "$BACKEND" sess-A
check "exit 2 (차단)" 2 "$RC"
teardown

echo "T8b Arduino 스케치(.ino)도 게이트 대상 — 실배포에서 발견된 누락"
setup
mkdir -p "$FIX/Circuits/IO-Board/ETH_LAN8720/docs/code_review/eth"
cat > "$FIX/Circuits/IO-Board/ETH_LAN8720/docs/code_review/eth/2026-05-21.md" <<'EOF'
| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `setup` | — | void | Serial init, SPI 핀 설정, CAN bus init | ETH_LAN8720.ino:43-57 |
EOF
echo "void setup(){}" > "$FIX/Circuits/IO-Board/ETH_LAN8720/ETH_LAN8720.ino"
hook PreToolUse Edit "Circuits/IO-Board/ETH_LAN8720/ETH_LAN8720.ino" sess-A
check "exit 2 (차단)" 2 "$RC"
has "표 행이 동봉됨" "Serial init, SPI 핀 설정"
teardown

echo "T8c vendored 의존성 폴더(.pio/libdeps)의 표는 후보에서 제외"
setup
mkdir -p "$FIX/pkg/.pio/libdeps/lib/docs/code_review/vendor" "$FIX/pkg"
echo '| 1 | `vendor_fn` | 벤더 예제 | widget.ino:9 |' \
  > "$FIX/pkg/.pio/libdeps/lib/docs/code_review/vendor/x.md"
echo "void loop(){}" > "$FIX/pkg/widget.ino"
hook PreToolUse Edit "pkg/widget.ino" sess-A
check "exit 2 (차단)" 2 "$RC"
has "'표 없음' 메시지" "함수표가 없습니다"
hasnt "vendored 표를 지목하지 않음" ".pio/libdeps"
teardown

echo "T9  표 미등재 파일 → **차단** (표를 먼저 만들고 진행한다 — §2 문언)"
setup
hook PreToolUse Edit "src/Comm/CAN/can_relay/can_relay/helper.py" sess-A
check "exit 2 (차단)" 2 "$RC"
has "표 작성을 요구" "인벤토리"
has "대상 파일 명시" "helper.py"
teardown

echo "T9b CODING_GATE=lenient → 표 미등재도 통과 (명시적 완화, 흔적 남음)"
setup
export CODING_GATE=lenient
hook PreToolUse Edit "src/Comm/CAN/can_relay/can_relay/helper.py" sess-A
check "exit 0 (통과)" 0 "$RC"
unset CODING_GATE
teardown

echo "T10 규칙 비활성(coding.md 부재) → 통과"
setup
rm -rf "$FIX/docs/claude_guideline"
hook PreToolUse Edit "$BACKEND" sess-A
check "exit 0 (통과)" 0 "$RC"
teardown

echo "T11 비코드 파일 → 통과"
setup
hook PreToolUse Write "README.md" sess-A
check "exit 0 (통과)" 0 "$RC"
teardown

echo "T12 allow 목록 override → 통과"
setup
mkdir -p "$FIX/.git/coding/reads"
echo "$BACKEND" > "$FIX/.git/coding/reads/sess-A.allow"
hook PreToolUse Edit "$BACKEND" sess-A
check "exit 0 (통과)" 0 "$RC"
teardown

echo "T13 CODING_GATE_SKIP=1 → 통과"
setup
export CODING_GATE_SKIP=1
hook PreToolUse Edit "$BACKEND" sess-A
check "exit 0 (통과)" 0 "$RC"
unset CODING_GATE_SKIP
teardown

echo "T14 표가 아예 하나도 없는 저장소에서도 차단 (부채 발생 지점을 열어두지 않는다)"
setup
rm -rf "$FIX/src/Comm/CAN/can_relay/docs" "$FIX/docs/code_review" \
       "$FIX/src/Actuators/motor_control/docs" "$FIX/src/Misc/notes/docs"
hook PreToolUse Edit "$BACKEND" sess-A
check "exit 2 (차단)" 2 "$RC"
has "표 작성을 요구" "인벤토리"
teardown

echo "T15 MultiEdit 도 게이트 대상"
setup
hook PreToolUse MultiEdit "$BACKEND" sess-A
check "exit 2 (차단)" 2 "$RC"
teardown

echo "T15b 저장소 경로가 공백으로 끝나도 동작 (git 출력 strip 이 이름 일부를 지움)"
setup
NEW="${FIX}dir "                      # 디렉터리 이름 자체가 공백으로 끝남
mv "$FIX" "$NEW" && FIX="$NEW" && ERRF="$FIX/.stderr"
hook PreToolUse Edit "$BACKEND" sess-A
check "exit 2 (차단)" 2 "$RC"
has "표 경로가 정상 산출됨" "$LOCALTBL"
teardown

echo "T15c vendored 패키지(조상에 LICENSE) → 표 요구 안 함"
setup
mkdir -p "$FIX/src/vendor/OrbbecSDK_ROS2/src"
echo "MIT" > "$FIX/src/vendor/OrbbecSDK_ROS2/LICENSE"
echo "def sdk_fn(): pass" > "$FIX/src/vendor/OrbbecSDK_ROS2/src/node.py"
hook PreToolUse Edit "src/vendor/OrbbecSDK_ROS2/src/node.py" sess-A
check "exit 0 (통과)" 0 "$RC"
teardown

echo "T15d 저장소 루트의 LICENSE 는 vendored 판정 근거가 아니다 (전체 무력화 방지)"
setup
echo "Apache-2.0" > "$FIX/LICENSE"
hook PreToolUse Edit "$BACKEND" sess-A
check "exit 2 (차단 유지)" 2 "$RC"
has "표를 지목함" "$LOCALTBL"
teardown

echo "T15e vendored 라도 그 패키지에 표가 있으면 선독을 요구한다"
setup
mkdir -p "$FIX/src/vendor/lib/docs/code_review/lib" "$FIX/src/vendor/lib/src"
echo "MIT" > "$FIX/src/vendor/lib/LICENSE"
printf '| # | 함수 | 기능 | 위치 |\n|---|---|---|---|\n| 1 | `f` | 예시 | mod.py:3 |\n' \
  > "$FIX/src/vendor/lib/docs/code_review/lib/2026-08-10.md"
echo "def f(): pass" > "$FIX/src/vendor/lib/src/mod.py"
hook PreToolUse Edit "src/vendor/lib/src/mod.py" sess-A
check "exit 2 (차단)" 2 "$RC"
teardown

echo "T16 잘못된 stdin(빈 입력) → 통과 (훅이 작업을 막지 않음)"
setup
printf '' | "$PY" "$HOOK" >/dev/null 2>"$ERRF"
RC=$?
check "exit 0" 0 "$RC"
teardown

echo
if [ "$FAIL" -eq 0 ]; then
  echo "✓ 전체 통과 ($PASS)"
  exit 0
else
  echo "✗ 실패 $FAIL / 통과 $PASS"
  exit 1
fi
