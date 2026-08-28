#!/usr/bin/env bash
# 빌드 전 점검 — 인터넷 없는 타깃에서 «무엇이 없는지» 를 먼저 알려준다.
#
# 타깃은 이미 tm-robot-4 가 도는 PC(Advantech, x86_64, Ubuntu 22.04, ROS2 humble)라
# ROS2·PyQt5·moveit 같은 기본은 이미 있다. 실제로 빠질 수 있는 것은 **웹 GUI 전용**
# 두 가지뿐이라 그것을 집중적으로 본다.
#
# 사용: bash deploy/check-deps.sh
# 종료코드: 0 = 빌드 가능 / 1 = 필수 항목 누락
set -u

WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROS_SETUP="${ROS_SETUP:-/opt/ros/humble/setup.bash}"
fail=0
warn=0

ok()   { echo "  [OK]   $*"; }
bad()  { echo "  [없음] $*"; fail=1; }
soft() { echo "  [주의] $*"; warn=1; }

echo "=== 1. 기본 도구 ==="
command -v colcon >/dev/null 2>&1 && ok "colcon" || bad "colcon — apt install python3-colcon-common-extensions"
[ -f "$ROS_SETUP" ] && ok "ROS2 ($ROS_SETUP)" || bad "ROS2 humble — $ROS_SETUP 가 없다"
command -v python3 >/dev/null 2>&1 && ok "python3 $(python3 -V 2>&1 | awk '{print $2}')" || bad "python3"

echo ""
echo "=== 2. 아키텍처 ==="
ARCH="$(uname -m)"
if [ "$ARCH" = "x86_64" ]; then
    ok "x86_64 — 동봉한 휠(deploy/offline/wheels)과 일치"
else
    soft "$ARCH — 동봉 휠은 x86_64 용이다. 이 기계에 맞는 휠이 따로 필요하다"
fi

echo ""
echo "=== 3. PyQt 화면에 필요한 것 ==="
# shellcheck disable=SC1090
set +u; [ -f "$ROS_SETUP" ] && source "$ROS_SETUP" >/dev/null 2>&1; set -u
python3 -c "import PyQt5" 2>/dev/null && ok "PyQt5" || bad "PyQt5 — apt install python3-pyqt5"
python3 -c "import cv2" 2>/dev/null && ok "opencv(cv2)" || soft "cv2 — 비전 기능에 필요"
python3 -c "import yaml" 2>/dev/null && ok "pyyaml" || bad "pyyaml"
python3 -c "import numpy" 2>/dev/null && ok "numpy" || bad "numpy"

echo ""
echo "=== 4. 웹 GUI 에 필요한 것 (여기가 빠지기 쉽다) ==="
MISSING_PY=""
# ⚠️ **실제 실행 조건과 똑같이** 시험해야 한다.
#    run·web_bridge.launch 는 PYTHONNOUSERSITE=1 로 노드를 띄운다. 그 변수는
#    ~/.local/lib/pythonX/site-packages 를 무시시키므로, `pip install --user`
#    로 깐 flask 는 **깔려 있어도 노드에서는 안 보인다.**
#    예전 이 검사는 평범한 python3 로 시험해 «[OK] flask» 라고 했는데 정작
#    브리지는 ModuleNotFoundError 로 죽었다(2026-08-27 팹). 같은 조건으로 본다.
VENDOR="$WS/vendor/pylibs"
if [ -d "$VENDOR" ]; then
    ok "vendor/pylibs ($(du -sh "$VENDOR" 2>/dev/null | cut -f1)) — 노드가 이 경로를 씁니다"
else
    soft "vendor/pylibs 없음 — ~/.local 은 PYTHONNOUSERSITE=1 때문에 안 보입니다"
fi
for m in fastapi uvicorn pydantic starlette flask waitress; do
    if PYTHONNOUSERSITE=1 PYTHONPATH="$VENDOR:${PYTHONPATH:-}" \
            python3 -c "import $m" 2>/dev/null; then
        ok "$m"
    else
        echo "  [없음] $m   (노드와 같은 조건에서 import 실패)"
        MISSING_PY="$MISSING_PY $m"
    fi
done
if [ -n "$MISSING_PY" ]; then
    echo ""
    echo "  →  인터넷 없이 설치: bash deploy/offline-install.sh"
    echo "     (동봉한 deploy/offline/wheels 에서 설치한다)"
    fail=1
fi

if [ -d "/opt/ros/humble/share/rosbridge_server" ]; then
    ok "rosbridge_server"
else
    soft "rosbridge_server — 없으면 웹 화면은 뜨지만 실시간 로봇 상태(관절·자세)가 안 온다."
    echo "         REST 기능(팔레트 티칭·레시피·조그)은 그대로 동작한다."
    echo "         설치하려면 인터넷 있는 곳에서: apt install ros-humble-rosbridge-server"
fi

echo ""
echo "=== 5. 워크스페이스 ==="
[ -d "$WS/src" ] && ok "src ($(ls "$WS/src" | wc -l) 개 그룹)" || bad "src 없음"
[ -f "$WS/webgui/dist/index.html" ] && ok "webgui/dist (빌드된 화면 — 그대로 서빙)" \
    || soft "webgui/dist 없음 — npm 이 있으면 deploy/build.sh --web-only, 없으면 화면이 안 뜬다"
[ -d "$WS/src/AI/engine/hailo" ] && ok "AI/engine/hailo" \
    || soft "AI/engine/hailo 없음 (압축에서 제외됨) — AI 검출 탭만 영향. 기존 tm-robot-4 의 것을 연결하면 된다"

echo ""
if [ "$fail" = "1" ]; then
    echo "✗ 필수 항목이 빠졌다 — 위 [없음] 을 먼저 해결한다."
    exit 1
fi
[ "$warn" = "1" ] && echo "△ 빌드는 가능하다. 위 [주의] 는 일부 기능만 영향." || echo "✓ 전부 갖춰졌다."
echo ""
echo "다음: bash deploy/build.sh"
exit 0
