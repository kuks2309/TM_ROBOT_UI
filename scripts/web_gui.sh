#!/usr/bin/env bash

set -o pipefail

WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# 프런트는 워크스페이스 안에 있다 (예전엔 데스크톱 절대경로였다 — 타깃에 없다).
WEB="$WS/webgui"

# ── 로봇 IP 결정 ──────────────────────────────────────────────────────────
# MK2·MK4 의 robot_ip 를 **둘 다** 두드려 5890(SCT, 명령 채널)이 열린 쪽을 쓴다.
# 둘 중 하나에는 붙는다는 전제(2026-08-27). ROS 를 소싱하지 않아도 돌게 yaml 만 읽는다.
resolve_robot_ip() {
  python3 - "$WS" <<'PYEOF' 2>/dev/null
import os, socket, sys, glob
try:
    import yaml
except Exception:
    sys.exit(1)
ws = sys.argv[1]
d = os.path.join(ws, 'src/TM_Robot_Task_Manager/config/robots')
fixed = (os.environ.get('TM_ROBOT_ID') or '').strip()
active = os.path.join(d, 'active.txt')
if not fixed and os.path.isfile(active):
    try:
        fixed = open(active, encoding='utf-8').read().strip().splitlines()[0].strip()
    except Exception:
        fixed = ''
items = []
for path in sorted(glob.glob(os.path.join(d, '*.yaml'))):
    try:
        data = yaml.safe_load(open(path, encoding='utf-8')) or {}
    except Exception:
        continue
    rid, ip = data.get('id') or os.path.splitext(os.path.basename(path))[0], data.get('robot_ip')
    if ip:
        items.append((rid, str(ip)))
items.sort(key=lambda t: (t[0] != fixed,))          # 확정 프로필을 앞으로
for rid, ip in items:
    s = socket.socket(); s.settimeout(1.0)
    try:
        if s.connect_ex((ip, 5890)) == 0:
            print(ip); sys.exit(0)
    except Exception:
        pass
    finally:
        s.close()
sys.exit(1)
PYEOF
}

ROBOT_IP="${ROBOT_IP:-$(resolve_robot_ip || true)}"
[ -n "$ROBOT_IP" ] && echo "· 응답한 로봇: $ROBOT_IP (5890)" \
                   || echo "· 두 로봇 모두 무응답 — tm_driver 는 기본값으로 뜹니다"
LOGS="$WS/.web_gui_logs"

SERVICES=(
  "tm_driver|-|install/tm_driver/lib/tm_driver/tm_driver|ros2 run tm_driver tm_driver robot_ip:=$ROBOT_IP"
  "카메라 브리지|6189|tm_camera_bridge.py|env PYTHONNOUSERSITE=1 python3 $WS/src/TM_Robot_Task_Manager/scripts/tm_camera_bridge.py"
  "rosbridge|9090|rosbridge_websocket|ros2 launch rosbridge_server rosbridge_websocket_launch.xml"
  "웹 브리지|8000|-|env PYTHONNOUSERSITE=1 ros2 run tm_web_bridge tm_web_bridge"
  "JPEG 재발행|-|jpeg_republish_node.py|env PYTHONNOUSERSITE=1 python3 $WS/src/tm_web_bridge/scripts/jpeg_republish_node.py"
  "MoveIt(move_group)|-|moveit_ros_move_group/move_group|ros2 launch tm20_moveit_config tm20_move_group_only.launch.py"
)

source_ros() {
  # shellcheck disable=SC1091
  source /opt/ros/humble/setup.bash 2>/dev/null || true
  # shellcheck disable=SC1091
  source "$WS/install/setup.bash" 2>/dev/null || true

  export ROS_LOCALHOST_ONLY=1
}

port_up() { ss -tln 2>/dev/null | grep -q ":$1 "; }
proc_up() { pgrep -f "$1" >/dev/null 2>&1; }

alive() {
  local port="$1" pat="$2"
  if [ "$port" != "-" ]; then port_up "$port"; return $?; fi
  if [ "$pat"  != "-" ]; then proc_up "$pat"; return $?; fi
  return 1
}

do_start() {
  source_ros
  mkdir -p "$LOGS"
  echo "=== 웹 GUI 스택 기동 ==="
  for s in "${SERVICES[@]}"; do
    IFS='|' read -r name port node cmd <<< "$s"
    if alive "$port" "$node"; then
      echo "  • $name — 이미 실행 중 (건너뜀)"
      continue
    fi
    local log="$LOGS/$(echo "$name" | tr -d ' ()가-힣' | tr -c 'a-zA-Z0-9' '_').log"
    echo "  ▸ $name 기동…"
    setsid nohup bash -c "$cmd" > "$log" 2>&1 < /dev/null &
    disown 2>/dev/null || true
    sleep 2
  done
  echo ""
  sleep 4
  do_status
}

do_stop() {
  echo "=== 웹 GUI 스택 정지 ==="
  pkill -f "tm20_move_group_only.launch.py" && echo "  ✓ MoveIt 정지"
  pkill -f "tm_camera_bridge.py"            && echo "  ✓ 카메라 브리지 정지"
  pkill -f "jpeg_republish_node.py"         && echo "  ✓ JPEG 재발행 정지"
  pkill -f "tm_web_bridge"                  && echo "  ✓ 웹 브리지 정지"
  pkill -f "rosbridge_websocket"            && echo "  ✓ rosbridge 정지"
  pkill -f "tm_driver"                      && echo "  ✓ tm_driver 정지"
  pkill -f "vite"                           && echo "  ✓ vite 정지"   # 예전 개발서버가 떠 있으면 정리
  echo "완료."
}

do_status() {
  source_ros
  echo "=== 상태 ==="
  local all_ok=1
  for s in "${SERVICES[@]}"; do
    IFS='|' read -r name port node _ <<< "$s"
    local label="$name"
    [ "$port" != "-" ] && label="$name  (:$port)"
    if alive "$port" "$node"; then
      echo "  ✓ $label"
    else
      echo "  ✗ $label  ← 안 뜸"; all_ok=0
    fi
  done

  echo ""
  echo "=== 로봇 / TMflow ==="
  if ping -c 1 -W 2 "$ROBOT_IP" >/dev/null 2>&1; then
    echo "  ✓ 로봇($ROBOT_IP) 응답"
  else
    echo "  ✗ 로봇($ROBOT_IP) 무응답 — 전원/네트워크 확인"; all_ok=0
  fi
  if grep -qs "On listen node" "$LOGS"/tm_driver*.log 2>/dev/null; then
    echo "  ✓ TMflow 프로젝트 실행 중 (Listen 노드 진입 확인)"
  else
    echo "  ? TMflow — 로봇 펜던트에서 프로젝트를 실행해야 함 (PC 에서 못 켬)"
  fi

  echo ""
  echo "=== 접속 주소 ==="
  echo "  이 PC        : http://localhost:8000"
  for ip in $(ip -4 addr show 2>/dev/null | grep -oE 'inet [0-9.]+' | awk '{print $2}' | grep -vE '^127\.|^172\.17\.'); do
    echo "  다른 기기    : http://$ip:8000"
  done
  echo ""
  [ "$all_ok" -eq 1 ] && echo "전부 정상." || echo "일부 미기동 — 로그: $LOGS/"
}

if [ ! -f "$WEB/dist/index.html" ]; then
  echo "⚠ $WEB/dist 가 없습니다 — 웹 화면이 안 뜹니다."
  echo "  빌드: bash $WS/deploy/build.sh --web-only   (npm 필요)"
fi

case "${1:-start}" in
  start)  do_start ;;
  stop)   do_stop ;;
  status) do_status ;;
  restart) do_stop; sleep 2; do_start ;;
  *) echo "사용법: $0 {start|stop|status|restart}"; exit 1 ;;
esac
