#!/usr/bin/env bash
# ros2-qos.test.sh — coding-ros2-qos.py 계약 테스트.
#
# 훅 계약(Claude Code PostToolUse): stdin JSON → stdout 이 안내로 주입, 항상 exit 0.
# **차단하지 않는다** — 판정이 아니라 결정 시점 전달이 목적이다.
#
# 배경: QoS 규칙은 ros2-coding.md §1 에 두 줄뿐이고 강제가 없다. 판정 규칙(RxO 매트릭스)은
# code_review/domains/ros2-review.md 에만 있어, 리뷰를 돌리지 않으면 적용되지 않는다.
# pub/sub 를 만드는 그 순간에 규칙을 전달해 매번 다시 묻는 상황을 없앤다.
#
# 실행: bash coding/tests/ros2-qos.test.sh
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="$DIR/../hooks/coding-ros2-qos.py"
PY="$(command -v python3 || command -v python)"
[ -n "$PY" ] || { echo "python3 없음"; exit 2; }
PASS=0; FAIL=0; FIX=""; OUT=""

setup() {
  FIX="$(mktemp -d)"; OUT="$FIX/.out"
  mkdir -p "$FIX/docs/claude_guideline/coding/domains" "$FIX/src"
  echo "# coding" > "$FIX/docs/claude_guideline/coding/coding.md"
  echo "# ros2 domain" > "$FIX/docs/claude_guideline/coding/domains/ros2-coding.md"
}
teardown() { [ -n "$FIX" ] && rm -rf "$FIX"; }

edit() {  # edit <rel> <new_string>
  "$PY" - "$1" "$2" "$FIX" <<'PYEOF' | "$PY" "$HOOK" >"$OUT" 2>&1
import json,sys
rel,new,fix=sys.argv[1],sys.argv[2],sys.argv[3]
print(json.dumps({"tool_name":"Edit","cwd":fix,
    "tool_input":{"file_path":fix+"/"+rel,"new_string":new}},ensure_ascii=False))
PYEOF
  RC=$?
}
has()   { if grep -qF -- "$2" "$OUT" 2>/dev/null; then printf '  ✓ %s\n' "$1"; PASS=$((PASS+1));
          else printf '  ✗ %s — "%s" 없음. 실제:\n%s\n' "$1" "$2" "$(sed 's/^/      /' "$OUT")"; FAIL=$((FAIL+1)); fi; }
empty() { if [ ! -s "$OUT" ]; then printf '  ✓ %s\n' "$1"; PASS=$((PASS+1));
          else printf '  ✗ %s — 출력 있음:\n%s\n' "$1" "$(sed 's/^/      /' "$OUT")"; FAIL=$((FAIL+1)); fi; }
check() { if [ "$2" = "$3" ]; then printf '  ✓ %s\n' "$1"; PASS=$((PASS+1));
          else printf '  ✗ %s — 기대 %s, 실제 %s\n' "$1" "$2" "$3"; FAIL=$((FAIL+1)); fi; }

echo "Q1  create_publisher 추가 → 안내"
setup; edit "src/n.py" 'self.pub = self.create_publisher(Twist, "/cmd_vel", 10)'
check "exit 0 (차단 아님)" 0 "$RC"
has "RxO 호환 규칙" "offered"
has "프로파일 안내" "best_effort"
has "토픽 표 등재 안내" "code_review"
has "검출한 호출 표시" "create_publisher"
teardown

echo "Q2  create_subscription 추가 → 안내"
setup; edit "src/n.py" 'self.sub = self.create_subscription(LaserScan, "/scan", self.cb, qos)'
check "exit 0" 0 "$RC"
has "RxO 호환 규칙" "offered"
teardown

echo "Q3  C++ 형태(create_publisher<T>) 도 검출"
setup; edit "src/n.cpp" 'pub_ = create_publisher<std_msgs::msg::Bool>("/estop", rclcpp::QoS(1));'
check "exit 0" 0 "$RC"
has "검출" "create_publisher"
teardown

echo "Q4  ROS2 무관 코드 → 무출력"
setup; edit "src/n.py" 'def add(a, b):
    return a + b'
check "exit 0" 0 "$RC"; empty "무출력"
teardown

echo "Q5  coding 룰 비활성 → 무출력"
setup; rm -rf "$FIX/docs/claude_guideline"
edit "src/n.py" 'self.create_publisher(Twist, "/cmd_vel", 10)'
check "exit 0" 0 "$RC"; empty "무출력"
teardown

echo "Q6  ros2 도메인 미설치 → 무출력 (도메인 훅)"
setup; rm -f "$FIX/docs/claude_guideline/coding/domains/ros2-coding.md"
edit "src/n.py" 'self.create_publisher(Twist, "/cmd_vel", 10)'
check "exit 0" 0 "$RC"; empty "무출력"
teardown

echo "Q7  문서 파일(.md) 안의 예시 코드 → 무출력"
setup; edit "docs/note.md" '예시: `self.create_publisher(Twist, "/cmd_vel", 10)`'
check "exit 0" 0 "$RC"; empty "무출력"
teardown

echo "Q8  잘못된 stdin → 무출력, exit 0"
setup; printf '' | "$PY" "$HOOK" >"$OUT" 2>&1; RC=$?
check "exit 0" 0 "$RC"; empty "무출력"
teardown

echo
if [ "$FAIL" -eq 0 ]; then echo "✓ 전체 통과 ($PASS)"; exit 0
else echo "✗ 실패 $FAIL / 통과 $PASS"; exit 1; fi
