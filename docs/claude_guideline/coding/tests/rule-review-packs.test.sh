#!/usr/bin/env bash
# rule-review-packs.test.sh — coding-rule-review.py 의 도메인 검출자 팩 계약.
#
# ros2 팩은 tests/ros2-rule-review.test.sh 가 맡고, 여기서는 concurrency·embedded·
# numeric·memory 팩을 잡는다. 훅은 **판정하지 않고 후보만 낸다** — 계약도 "무엇을
# 지목했나"이며, 지목하지 말아야 할 때 침묵하는지(음성 대조)를 함께 잡는다.
#
# 실행: bash coding/tests/rule-review-packs.test.sh
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="$DIR/../hooks/coding-rule-review.py"
PY="$(command -v python3 || command -v python)"
[ -n "$PY" ] || { echo "python3 없음"; exit 2; }

PASS=0; FAIL=0; FIX=""; ERRF=""; TR=""; RC=0

setup() {  # setup <도메인...>
  FIX="$(mktemp -d)"; ERRF="$FIX/.stderr"; TR="$FIX/transcript.jsonl"
  mkdir -p "$FIX/docs/claude_guideline/coding/domains" "$FIX/src"
  echo "# coding 규칙" > "$FIX/docs/claude_guideline/coding/coding.md"
  for d in "$@"; do echo "# $d 규칙" > "$FIX/docs/claude_guideline/coding/domains/$d-coding.md"; done
  printf '{"type":"user","message":{"content":"작업해줘"}}\n' > "$TR"
}
teardown() { [ -n "$FIX" ] && rm -rf "$FIX"; }

src() {
  local rel="$1"; mkdir -p "$FIX/$(dirname "$rel")"; cat > "$FIX/$rel"
  "$PY" - "$TR" "$FIX/$rel" <<'PYEOF'
import json, sys
tr, path = sys.argv[1], sys.argv[2]
with open(tr, "a", encoding="utf-8") as f:
    f.write(json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "t%d" % (abs(hash(path)) % 9999), "name": "Edit",
         "input": {"file_path": path}}]}}, ensure_ascii=False) + "\n")
PYEOF
}

review() {
  printf '{"transcript_path":"%s","cwd":"%s","session_id":"s","stop_hook_active":false}' \
    "$TR" "$FIX" | "$PY" "$HOOK" >/dev/null 2>"$ERRF"
  RC=$?
  grep -qE "SyntaxError|Traceback|can't open file" "$ERRF" 2>/dev/null && RC="ERROR(훅 실행 실패)"
}
check() { if [ "$2" = "$3" ]; then printf '  ✓ %s\n' "$1"; PASS=$((PASS+1));
          else printf '  ✗ %s — 기대 %s, 실제 %s. 출력:\n%s\n' "$1" "$2" "$3" \
               "$(sed 's/^/      /' "$ERRF" 2>/dev/null)"; FAIL=$((FAIL+1)); fi; }
has()   { if grep -qF -- "$2" "$ERRF" 2>/dev/null; then printf '  ✓ %s\n' "$1"; PASS=$((PASS+1));
          else printf '  ✗ %s — "%s" 없음. 실제:\n%s\n' "$1" "$2" \
               "$(sed 's/^/      /' "$ERRF" 2>/dev/null)"; FAIL=$((FAIL+1)); fi; }
hasnt() { if grep -qF -- "$2" "$ERRF" 2>/dev/null; then printf '  ✗ %s — "%s" 있음:\n%s\n' \
               "$1" "$2" "$(sed 's/^/      /' "$ERRF")"; FAIL=$((FAIL+1));
          else printf '  ✓ %s\n' "$1"; PASS=$((PASS+1)); fi; }

echo "P1  concurrency — lock 보유 중 blocking / async 안 blocking"
setup concurrency; src src/w.py <<'EOF'
import threading, time
lock = threading.Lock()
def slow():
    with lock:
        time.sleep(1.0)
def fast():
    with lock:
        x = 1
    time.sleep(1.0)
async def handler():
    time.sleep(0.5)
EOF
review; check "종료 차단" 2 "$RC"
has   "잠금 중 blocking 지목"   "concurrency §2 잠금 중 blocking"
has   "slow 의 sleep 지목"      "w.py:5"
hasnt "lock 밖 sleep 미지목"    "w.py:9"
has   "async blocking 지목"     "concurrency §4 async blocking"
teardown

echo "P2  concurrency — spurious wakeup / 전역"
setup concurrency; src src/w.py <<'EOF'
import threading
state = 0
cv = threading.Condition()
def waiter():
    global state
    if not state:
        cv.wait()
def good():
    while not state:
        cv.wait()
EOF
review
has   "if 대기 지목"      "concurrency §3 spurious wakeup"
has   "global 지목"       "concurrency §1 공유 상태"
teardown

echo "P3  embedded — ISR 안 heavy / 동적 할당 / busy-wait"
setup embedded; src src/m.c <<'EOF'
#include <stdio.h>
volatile int flag;
void TIM2_IRQHandler(void) {
    printf("tick\n");
}
void setup(void) {
    char *b = malloc(64);
    HAL_Delay(100);
}
EOF
review; check "종료 차단" 2 "$RC"
has "ISR 규율 지목"     "embedded §1 ISR 규율"
has "동적 할당 지목"    "embedded §2 동적 할당"
has "busy-wait 지목"    "embedded §3 busy-wait"
teardown

echo "P4  numeric — 부동소수 == / acos clamp / 각도 변환 / 쿼터니언"
setup numeric; src src/n.py <<'EOF'
import math
def f(a, b):
    if a == 1.0:
        return 0
    t = math.acos(b)
    d = a * 180.0 / math.pi
    q = Quaternion(0, 0, 0, 1)
    return t, d, q
EOF
review; check "종료 차단" 2 "$RC"
has "부동소수 비교 지목" "numeric §3 부동소수 비교"
has "정의역 지목"        "numeric §3 정의역"
has "단위 변환 지목"     "numeric §1 단위 변환"
has "쿼터니언 지목"      "numeric §2 쿼터니언"
teardown

echo "P5  numeric — clamp·normalize 하면 침묵 (음성 대조)"
setup numeric; src src/n.py <<'EOF'
import math
def f(b):
    t = math.acos(max(-1.0, min(1.0, b)))
    q = Quaternion(0, 0, 0, 1).normalize()
    return t, q
EOF
review; check "통과" 0 "$RC"; teardown

echo "P6  memory — 맨손 new / 안전하지 않은 문자열 / 짝 없음"
setup memory; src src/a.cpp <<'EOF'
#include <cstring>
void f() {
    Foo* p = new Foo();
    char buf[8];
    strcpy(buf, "abcdefghijk");
}
EOF
review; check "종료 차단" 2 "$RC"
has "소유권 지목"   "memory §1 소유권"
has "버퍼 지목"     "memory §3 버퍼"
has "짝 지목"       "memory §2 할당·해제 짝"
teardown

echo "P7  memory — 스마트 포인터면 침묵 (음성 대조)"
setup memory; src src/a.cpp <<'EOF'
#include <memory>
void f() {
    auto p = std::make_unique<Foo>();
    char buf[8];
    snprintf(buf, sizeof(buf), "%d", 1);
}
EOF
review; check "통과" 0 "$RC"; teardown

echo "P8  도메인 미설치면 그 팩은 침묵 (음성 대조)"
setup ros2; src src/w.py <<'EOF'
import threading, time
lock = threading.Lock()
def slow():
    with lock:
        time.sleep(1.0)
EOF
review; check "concurrency 미설치 → 통과" 0 "$RC"; teardown

echo "P9  여러 도메인 동시 설치 — 각 팩이 자기 것만 지목"
setup concurrency numeric; src src/x.py <<'EOF'
import threading, math, time
lock = threading.Lock()
def f(a):
    with lock:
        time.sleep(1)
    return a == 2.0
EOF
review
has "concurrency 지목" "concurrency §2"
has "numeric 지목"     "numeric §3 부동소수"
teardown

echo
if [ "$FAIL" -eq 0 ]; then echo "✓ 전체 통과 ($PASS)"; exit 0
else echo "✗ 실패 $FAIL / 통과 $PASS"; exit 1; fi
