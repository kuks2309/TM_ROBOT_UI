#!/usr/bin/env bash
# ros2-rule-review.test.sh — coding-rule-review.py 계약 테스트 (ros2 검출자 팩).
#
# 훅 계약(Claude Code Stop): stdin JSON(cwd·transcript_path·stop_hook_active) →
#   stderr + exit 2 = 종료 1회 차단(모델이 지목된 지점을 확인·보완), 그 외 exit 0.
#
# 본 훅은 **판정하지 않는다** — 후보만 지목한다. 그래서 계약도 "무엇을 지목했나"이지
# "무엇이 위반인가"가 아니다. 음성 대조(지목하지 말아야 할 때 침묵)를 함께 잡는다.
#
# 실행: bash coding/tests/ros2-rule-review.test.sh
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="$DIR/../hooks/coding-rule-review.py"
PY="$(command -v python3 || command -v python)"
[ -n "$PY" ] || { echo "python3 없음"; exit 2; }

PASS=0; FAIL=0; FIX=""; ERRF=""; TR=""; RC=0

setup() {  # setup [--no-ros2]
  FIX="$(mktemp -d)"; ERRF="$FIX/.stderr"; TR="$FIX/transcript.jsonl"
  mkdir -p "$FIX/docs/claude_guideline/coding/domains" "$FIX/src"
  echo "# coding 규칙" > "$FIX/docs/claude_guideline/coding/coding.md"
  [ "${1:-}" = "--no-ros2" ] || \
    echo "# ros2 규칙" > "$FIX/docs/claude_guideline/coding/domains/ros2-coding.md"
  printf '{"type":"user","message":{"content":"작업해줘"}}\n' > "$TR"
}
teardown() { [ -n "$FIX" ] && rm -rf "$FIX"; }

# rec <절대경로> — 파일을 만들지 않고 "이번 턴에 고친 것" 으로만 기록
rec() {
  "$PY" - "$TR" "$1" <<'PYEOF'
import json, sys
tr, path = sys.argv[1], sys.argv[2]
with open(tr, "a", encoding="utf-8") as f:
    f.write(json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "t%d" % (abs(hash(path)) % 9999), "name": "Edit",
         "input": {"file_path": path}}]}}, ensure_ascii=False) + "\n")
PYEOF
}

# src <상대경로> — heredoc 본문을 파일로 쓰고 이번 턴 수정으로 기록
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

# gitfix — 지금까지 쓴 파일을 "이미 있던 것"(git 추적)으로 만든다. 이후 src 로 만든
# 파일은 미추적 = 이번에 새로 만든 것. §0 의 신규 판정이 이 경계를 쓴다.
gitfix() {
  # core.excludesFile 중화 — 개발자 전역 gitignore 가 `*.py` 를 걸면 추적이 안 돼
  # "기존 파일" 경계가 조용히 사라진다. 실패는 삼키지 않고 바로 멈춘다.
  git -c init.defaultBranch=main -C "$FIX" init -q >/dev/null 2>&1 \
    && git -c core.excludesFile=/dev/null -C "$FIX" add -A >/dev/null 2>&1 \
    && git -C "$FIX" -c user.name=t -c user.email=t@t -c commit.gpgsign=false \
         commit -qm init --no-verify >/dev/null 2>&1 \
    || { echo "  ✗ gitfix 실패 — git 픽스처를 만들 수 없음"; FAIL=$((FAIL+1)); return 1; }
}

review() {  # review [stop_hook_active]
  printf '{"transcript_path":"%s","cwd":"%s","session_id":"s","stop_hook_active":%s}' \
    "$TR" "$FIX" "${1:-false}" | "$PY" "$HOOK" >/dev/null 2>"$ERRF"
  RC=$?
  grep -qE "SyntaxError|Traceback|can't open file" "$ERRF" 2>/dev/null && RC="ERROR(훅 실행 실패)"
}

check() { if [ "$2" = "$3" ]; then printf '  ✓ %s\n' "$1"; PASS=$((PASS+1));
          else printf '  ✗ %s — 기대 %s, 실제 %s. 출력:\n%s\n' "$1" "$2" "$3" \
               "$(sed 's/^/      /' "$ERRF" 2>/dev/null)"; FAIL=$((FAIL+1)); fi; }
has()   { if grep -qF -- "$2" "$ERRF" 2>/dev/null; then printf '  ✓ %s\n' "$1"; PASS=$((PASS+1));
          else printf '  ✗ %s — "%s" 없음. 실제:\n%s\n' "$1" "$2" \
               "$(sed 's/^/      /' "$ERRF" 2>/dev/null)"; FAIL=$((FAIL+1)); fi; }
hasnt() { if grep -qF -- "$2" "$ERRF" 2>/dev/null; then printf '  ✗ %s — "%s" 가 들어있음:\n%s\n' \
               "$1" "$2" "$(sed 's/^/      /' "$ERRF")"; FAIL=$((FAIL+1));
          else printf '  ✓ %s\n' "$1"; PASS=$((PASS+1)); fi; }

echo "R1  §1 QoS — 깊이 정수만 넘긴 pub/sub 은 지목, 프로파일 명시는 침묵"
setup; src src/n.py <<'EOF'
import rclpy
from rclpy.qos import QoSProfile
class N:
    def __init__(self):
        self.a = self.create_publisher(Twist, "/cmd_vel", 10)
        self.b = self.create_subscription(Scan, "/scan", self.cb, SENSOR_QOS)
        self.c = self.create_publisher(Odom, "/odom", QoSProfile(depth=5))
EOF
review; check "종료 차단" 2 "$RC"
has   "깊이 정수 호출 지목"     "ros2 §1 QoS"
has   "줄번호 5 지목"           "n.py:5"
hasnt "프로파일 상수는 미지목"  "n.py:6"
hasnt "빌더 호출은 미지목"      "n.py:7"
has   "판정이 아님을 명시"      "판정이 아니라 후보"
teardown

echo "R2  §2 콜백 blocking — 콜백 안만 지목, 밖은 침묵"
setup; src src/n.py <<'EOF'
import rclpy, time
class N:
    def __init__(self):
        self.s = self.create_subscription(Scan, "/scan", self.on_scan, SENSOR_QOS)
        time.sleep(0.1)
    def on_scan(self, msg):
        time.sleep(0.5)
    def helper(self):
        time.sleep(2.0)
EOF
review; check "종료 차단" 2 "$RC"
has   "콜백 안 blocking 지목" "ros2 §2 콜백 blocking"
has   "on_scan 지목"          "n.py:7"
hasnt "__init__ 은 미지목"    "n.py:5"
hasnt "일반 함수는 미지목"    "n.py:9"
teardown

echo "R3  §3 파라미터 — declare 없는 get_parameter 만 지목"
setup; src src/n.py <<'EOF'
import rclpy
class N:
    def __init__(self):
        self.declare_parameter("wheel_base", 1.0)
        self.p = self.create_publisher(Twist, "/cmd_vel", QOS)
        a = self.get_parameter("wheel_base").value
        b = self.get_parameter("max_speed").value
EOF
review; check "종료 차단" 2 "$RC"
has   "미선언 파라미터 지목" "ros2 §3 파라미터"
has   "max_speed 지목"       "max_speed"
hasnt "선언된 것은 미지목"   "wheel_base"
teardown

echo "R4  §4 인터페이스 — .msg 수정은 공개표면"
setup; src msg/Pose2D.msg <<'EOF'
float64 x
EOF
review; check "종료 차단" 2 "$RC"
has "인터페이스 지목" "ros2 §4 인터페이스"
has "ADR 요구"        "ADR"
teardown

echo "R5  묶음 출력 — 같은 파일·항목의 반복은 한 줄"
setup; src src/n.py <<'EOF'
import rclpy
class N:
    def __init__(self):
        self.a = self.create_publisher(A, "/a", 10)
        self.b = self.create_publisher(B, "/b", 10)
        self.c = self.create_publisher(C, "/c", 10)
EOF
review
check "지목 줄 1개로 묶임" 1 "$(grep -c 'ros2 §1 QoS' "$ERRF")"
has   "줄번호 나열"        "n.py:4, 5, 6"
teardown

echo "R6  침묵해야 하는 경우 (음성 대조)"
setup --no-ros2; src src/n.py <<'EOF'
import rclpy
class N:
    def __init__(self):
        self.a = self.create_publisher(A, "/a", 10)
EOF
review; check "ros2 도메인 미설치 → 통과" 0 "$RC"; teardown

setup; src src/n.py <<'EOF'
import rclpy
class N:
    def __init__(self):
        self.a = self.create_publisher(A, "/a", 10)
EOF
review true; check "stop_hook_active → 1패스만" 0 "$RC"; teardown

setup; src src/plain.py <<'EOF'
def f():
    return 1
EOF
review; check "ROS2 아닌 파일 → 통과" 0 "$RC"; teardown

setup; src src/n.py <<'EOF'
import rclpy
class N:
    def __init__(self):
        self.a = self.create_publisher(A, "/a", 10)
EOF
CODING_REVIEW_SKIP=1 review; check "우회 스위치 → 통과" 0 "$RC"; teardown

setup; printf '{"type":"user","message":{"content":"질문만"}}\n' > "$TR"
review; check "수정 0건 → 통과" 0 "$RC"; teardown

setup
mkdir -p "$FIX/docs/sw_structure/n"
cat > "$FIX/docs/sw_structure/n/table.md" <<'EOF'
| 토픽 | 타입 | QoS | 위치 |
|---|---|---|---|
| `/scan` | `sensor_msgs/LaserScan` | SensorData | n.py:5 |
EOF
src src/n.py <<'EOF'
import rclpy
from rclpy.qos import qos_profile_sensor_data
class N:
    def __init__(self):
        self.a = self.create_subscription(Scan, "/scan", self.cb, qos_profile_sensor_data)
EOF
review; check "QoS 명시 + 표 등재 + 위반 없음 → 통과" 0 "$RC"; teardown

echo "R7  토픽 표 미등재 — 리터럴 토픽이 표에 없으면 지목"
setup; src src/n.py <<'EOF'
import rclpy
class N:
    def __init__(self):
        self.a = self.create_publisher(Odom, "/odom", SENSOR_QOS)
        self.b = self.create_publisher(Twist, "/cmd_vel", SENSOR_QOS)
EOF
mkdir -p "$FIX/docs/sw_structure/n"
cat > "$FIX/docs/sw_structure/n/table.md" <<'EOF'
| 토픽 | 타입 | QoS | 위치 |
|---|---|---|---|
| `/odom` | `nav_msgs/Odometry` | reliable 10 | n.py:4 |
EOF
review; check "종료 차단" 2 "$RC"
has   "미등재 토픽 지목"   "ros2 표 토픽 미등재"
has   "/cmd_vel 지목"      "/cmd_vel"
hasnt "등재된 토픽 미지목" "\`/odom\` 이 토픽 표에"
teardown

echo "R8  QoS 짝 — RxO 불호환만 지목, 호환은 침묵"
setup
mkdir -p "$FIX/docs/sw_structure/n"
cat > "$FIX/docs/sw_structure/n/table.md" <<'EOF'
| 토픽 | 타입 | QoS | 위치 |
|---|---|---|---|
| `/scan` | `sensor_msgs/LaserScan` | best_effort | pub.py:4 |
| `/state` | `std_msgs/Bool` | reliable | pub.py:5 |
EOF
src src/pub.py <<'EOF'
import rclpy
from rclpy.qos import QoSProfile, ReliabilityPolicy
class P:
    def __init__(self):
        self.a = self.create_publisher(Scan, "/scan", QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT))
        self.b = self.create_publisher(Bool, "/state", QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE))
EOF
src src/sub.py <<'EOF'
import rclpy
from rclpy.qos import QoSProfile, ReliabilityPolicy
class S:
    def __init__(self):
        self.a = self.create_subscription(Scan, "/scan", self.cb, QoSProfile(depth=5, reliability=ReliabilityPolicy.RELIABLE))
        self.b = self.create_subscription(Bool, "/state", self.cb, QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE))
EOF
review; check "종료 차단" 2 "$RC"
has   "불호환 지목"          "ros2 §1 QoS 짝 불호환"
has   "사유 표시"            "발행 BEST_EFFORT ↔ 구독 RELIABLE"
has   "양쪽 위치 표시"       "pub.py:5"
hasnt "호환 짝은 미지목"     "\`/state\` —"
teardown

echo "R9  QoS 를 못 푸는 짝은 판정하지 않는다 (음성 대조)"
setup
mkdir -p "$FIX/docs/sw_structure/n"
cat > "$FIX/docs/sw_structure/n/table.md" <<'EOF'
| 토픽 | 타입 | QoS | 위치 |
|---|---|---|---|
| `/scan` | `sensor_msgs/LaserScan` | ? | pub.py:4 |
EOF
src src/pub.py <<'EOF'
import rclpy
from mypkg.profiles import WEIRD_QOS
class P:
    def __init__(self):
        self.a = self.create_publisher(Scan, "/scan", WEIRD_QOS)
EOF
src src/sub.py <<'EOF'
import rclpy
from mypkg.profiles import OTHER_QOS
class S:
    def __init__(self):
        self.a = self.create_subscription(Scan, "/scan", self.cb, OTHER_QOS)
EOF
review; check "못 푸는 QoS → 통과" 0 "$RC"; teardown

echo "R10 §0 언어 — 새로 만든 rclpy 노드만 지목, 기존 파일·UI 파일은 침묵"
setup; src src/old_node.py <<'EOF'
import rclpy
from rclpy.node import Node
class Old(Node):
    def __init__(self):
        super().__init__("old")
        self.t = self.create_timer(0.1, self.on_tick)
    def on_tick(self):
        pass
EOF
gitfix                      # 여기까지가 "이미 있던 파일"
src src/new_node.py <<'EOF'
import rclpy
from rclpy.node import Node
class New(Node):
    def __init__(self):
        super().__init__("new")
        self.t = self.create_timer(0.1, self.on_tick)
    def on_tick(self):
        pass
EOF
src src/new_ui.py <<'EOF'
import rclpy
from rclpy.node import Node
from PyQt5.QtWidgets import QWidget
class Panel(QWidget):
    def __init__(self):
        self.node = Node("panel")
EOF
src src/new_rqt.py <<'EOF'
import rclpy
from rclpy.node import Node
from python_qt_binding.QtWidgets import QWidget
class Plugin(QWidget):
    def __init__(self):
        self.node = Node("rqt")
EOF
src src/new_util.py <<'EOF'
import rclpy
def stamp(node):
    return node.get_clock().now()
EOF
review; check "종료 차단" 2 "$RC"
has   "새 rclpy 노드 지목"        "ros2 §0 노드 언어"
has   "새 파일 지목"              "src/new_node.py:1"
has   "금지가 아니라 사유 기록"   "사유 기록"
hasnt "기존 파일은 미지목"        "src/old_node.py:1"
hasnt "PyQt5 동반 파일은 미지목"  "src/new_ui.py:1"
hasnt "python_qt_binding 도 UI"   "src/new_rqt.py:1"
hasnt "노드 꼴 아닌 파일 미지목"  "src/new_util.py:1"
teardown

echo "R11 §0 빌드 타입 — 새 ament_python package.xml 만 지목"
setup; src pkg_old/package.xml <<'EOF'
<package format="3">
  <name>old_ui</name>
  <export><build_type>ament_python</build_type></export>
</package>
EOF
gitfix
src pkg_new/package.xml <<'EOF'
<package format="3">
  <name>new_pkg</name>
  <export><build_type>ament_python</build_type></export>
</package>
EOF
src pkg_cmake/package.xml <<'EOF'
<package format="3">
  <name>cmake_pkg</name>
  <export><build_type>ament_cmake</build_type></export>
</package>
EOF
src pkg_cmakepy/package.xml <<'EOF'
<package format="3">
  <name>cmakepy_pkg</name>
  <export><build_type>ament_cmake_python</build_type></export>
</package>
EOF
review; check "종료 차단" 2 "$RC"
has   "새 ament_python 지목"   "ros2 §0 빌드 타입"
has   "위치 지목"              "pkg_new/package.xml:3"
hasnt "기존 패키지는 미지목"   "pkg_old/package.xml:3"
hasnt "ament_cmake 는 미지목"  "pkg_cmake/package.xml:3"
hasnt "제3의 값도 미지목"      "pkg_cmakepy/package.xml:3"
teardown

echo "R12 §0 UI — PyQt5 아닌 import 줄만 지목(기존 파일도 줄 단위로 온다)"
setup; src src/panel.py <<'EOF'
import sys
import tkinter as tk
from PyQt5.QtWidgets import QWidget
from PySide6 import QtCore
import wx
# import tkinter  — 주석은 import 줄이 아니다
EOF
gitfix
review; check "종료 차단" 2 "$RC"
has   "UI 이탈 지목"          "ros2 §0 UI 프레임워크"
has   "이탈 줄만 묶임"        "src/panel.py:2, 4, 5"
has   "기존분은 두라고 전달"  "기존 파일이면 그대로 둔다"
hasnt "PyQt5 줄(3)은 미지목"  "src/panel.py:3"
hasnt "주석 줄(6)은 미지목"   "src/panel.py:2, 4, 5, "
teardown

echo "R13 git 저장소가 아니면 언어·빌드 타입은 침묵 (음성 대조)"
setup; src src/new_node.py <<'EOF'
import rclpy
from rclpy.node import Node
class New(Node):
    def __init__(self):
        super().__init__("new")
        self.t = self.create_timer(0.1, self.on_tick)
    def on_tick(self):
        pass
EOF
src pkg/package.xml <<'EOF'
<package format="3"><export><build_type>ament_python</build_type></export></package>
EOF
review; check "git 없음 → 통과" 0 "$RC"; teardown

echo "R14 §0 — 추적 중인 한글 이름 파일을 신규로 보지 않는다 (quotePath 고정)"
setup; src "src/한글노드.py" <<'EOF'
import rclpy
from rclpy.node import Node
class N(Node):
    def __init__(self):
        super().__init__("n")
        self.t = self.create_timer(0.1, self.on_tick)
    def on_tick(self):
        pass
EOF
gitfix
review; check "추적 한글 파일 → 통과" 0 "$RC"; teardown

echo "R15 cwd 밖 파일을 같은 턴에 고쳐도 §0 지목이 살아 있다 (git 호출 전체 실패 방지)"
setup
OUT="$(mktemp -d)"; printf 'import os\n' > "$OUT/tool.py"
src src/new_node.py <<'EOF'
import rclpy
from rclpy.node import Node
class New(Node):
    def __init__(self):
        super().__init__("new")
        self.t = self.create_timer(0.1, self.on_tick)
    def on_tick(self):
        pass
EOF
gitfix
src src/newer_node.py <<'EOF'
import rclpy
from rclpy.node import Node
class Newer(Node):
    def __init__(self):
        super().__init__("newer")
        self.t = self.create_timer(0.1, self.on_tick)
    def on_tick(self):
        pass
EOF
rec "$OUT/tool.py"                 # 저장소 밖 경로를 같은 턴 수정으로 기록
review; check "종료 차단" 2 "$RC"
has   "cwd 밖 파일이 있어도 지목"  "ros2 §0 노드 언어"
has   "새 파일 지목"               "src/newer_node.py:1"
hasnt "cwd 밖 파일 자체는 미지목"  "tool.py"
rm -rf "$OUT"; teardown

echo "R16 한 파일을 여러 번 고쳐도 줄번호가 겹치지 않는다"
setup; gitfix
src src/new_node.py <<'EOF'
import rclpy
from rclpy.node import Node
class New(Node):
    def __init__(self):
        super().__init__("new")
        self.t = self.create_timer(0.1, self.on_tick)
    def on_tick(self):
        pass
EOF
rec "$FIX/src/new_node.py"; rec "$FIX/src/new_node.py"
review; check "종료 차단" 2 "$RC"
has   "한 번만 지목"      "src/new_node.py:1"
hasnt "줄번호 중복 없음"  "src/new_node.py:1, 1"
teardown

echo "R17 stage 된 뒤에는 지목하지 않는다 — 경계는 git 인덱스다 (명시 고정)"
setup; gitfix
src src/new_node.py <<'EOF'
import rclpy
from rclpy.node import Node
class New(Node):
    def __init__(self):
        super().__init__("new")
        self.t = self.create_timer(0.1, self.on_tick)
    def on_tick(self):
        pass
EOF
git -c core.excludesFile=/dev/null -C "$FIX" add src/new_node.py >/dev/null 2>&1
review; check "인덱스에 들어가면 미지목" 0 "$RC"; teardown

echo "R18 상한에 걸려 잘린 묶음은 **어느 항목이 잘렸는지** 함께 낸다"
setup
for i in $(seq 1 13); do
  src "src/f$i.py" <<'EOF'
import rclpy
msg.header.frame_id = "base_link"
EOF
done
gitfix
src src/new_node.py <<'EOF'
import rclpy
from rclpy.node import Node
class New(Node):
    def __init__(self):
        super().__init__("new")
        self.t = self.create_timer(0.1, self.on_tick)
    def on_tick(self):
        pass
EOF
review; check "종료 차단" 2 "$RC"
has   "잘린 수·상한"    "외 2 묶음(상한 12)"
has   "잘린 항목 이름"  "ros2 §4 프레임 · ros2 §0 노드 언어"
teardown

echo
if [ "$FAIL" -eq 0 ]; then echo "✓ 전체 통과 ($PASS)"; exit 0
else echo "✗ 실패 $FAIL / 통과 $PASS"; exit 1; fi
