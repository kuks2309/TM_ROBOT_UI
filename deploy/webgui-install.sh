#!/usr/bin/env bash
# 웹 GUI 자동 부팅 등록 — systemd 유닛을 만들고 설치한다.
#
# 설치만 한다. **자동 시작은 켜지 않는다** — 켜고 끄는 것은
# webgui-enable.sh / webgui-disable.sh 가 맡는다. 설치와 활성을 나눠야
# "설치했더니 갑자기 로봇 화면이 뜬다" 같은 일이 없다.
#
# 사용:
#   sudo bash deploy/webgui-install.sh                 # 현재 사용자·워크스페이스로 설치
#   sudo bash deploy/webgui-install.sh --robot mk4     # 로봇 프로필을 함께 고정
#   sudo bash deploy/webgui-install.sh --dry-run       # 만들 유닛만 출력하고 끝
#
# 종료코드: 0 성공 / 1 실패
set -u

WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_NAME="tm-webgui.service"
UNIT_PATH="/etc/systemd/system/$UNIT_NAME"
ENV_PATH="/etc/default/tm-webgui"
ROS_SETUP="${ROS_SETUP:-/opt/ros/humble/setup.bash}"

RUN_USER="${SUDO_USER:-$USER}"
ROBOT_ID=""
DRY_RUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --robot) ROBOT_ID="${2:-}"; shift 2 ;;
        --user) RUN_USER="${2:-}"; shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
        *) echo "알 수 없는 인자: $1"; exit 1 ;;
    esac
done

# ---------------------------------------------------------------- 사전 확인
fail=0
[ -f "$ROS_SETUP" ] || { echo "✗ ROS setup 없음: $ROS_SETUP"; fail=1; }
[ -f "$WS/install/setup.bash" ] || {
    echo "✗ 워크스페이스가 빌드되지 않았습니다: $WS/install/setup.bash"
    echo "  먼저: bash $WS/deploy/build.sh"
    fail=1
}
[ -f "$WS/webgui/dist/index.html" ] || {
    echo "⚠ webgui/dist 가 없습니다 — 브리지는 뜨지만 화면이 안 나옵니다."
    echo "  먼저: bash $WS/deploy/build.sh --web-only"
}
id "$RUN_USER" >/dev/null 2>&1 || { echo "✗ 사용자 없음: $RUN_USER"; fail=1; }
[ "$fail" = "0" ] || exit 1

# 로봇 프로필: 인자로 안 주면 워크스페이스의 active.txt 를 본다
ACTIVE_FILE="$WS/src/TM_Robot_Task_Manager/config/robots/active.txt"
if [ -z "$ROBOT_ID" ] && [ -f "$ACTIVE_FILE" ]; then
    ROBOT_ID="$(head -1 "$ACTIVE_FILE" | tr -d '[:space:]')"
fi

ENV_BODY="# tm-webgui 환경설정 — 유닛을 고치지 말고 여기를 고친다.
# 로봇 기종(mk2 / mk4). 비우면 IP 로 자동 판정하고, 그래도 못 정하면 미확정으로 뜬다.
TM_ROBOT_ID=$ROBOT_ID
# 웹 GUI 정적 파일 경로. 비우면 워크스페이스에서 자동으로 찾는다.
TM_WEBGUI_DIST=$WS/webgui/dist
"

UNIT_BODY="[Unit]
Description=TM Robot 웹 GUI (tm_web_bridge + rosbridge)
Documentation=file://$WS/BUILD_COMMANDS.md
# 네트워크가 올라온 뒤에 뜬다 — rosbridge 가 포트를 연다.
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$WS
EnvironmentFile=-$ENV_PATH
# ros2 launch 는 자식 프로세스를 여럿 띄운다. 정지 시 그룹째 정리해야 좀비가 남지 않는다.
KillMode=control-group
KillSignal=SIGINT
TimeoutStopSec=20
Restart=on-failure
RestartSec=5
ExecStart=/bin/bash -lc 'source $ROS_SETUP && source $WS/install/setup.bash && exec ros2 launch tm_web_bridge web_bridge.launch.py'

[Install]
WantedBy=multi-user.target
"

if [ "$DRY_RUN" = "1" ]; then
    echo "===== $ENV_PATH ====="; echo "$ENV_BODY"
    echo "===== $UNIT_PATH ====="; echo "$UNIT_BODY"
    exit 0
fi

if [ "$(id -u)" != "0" ]; then
    echo "✗ 설치에는 root 권한이 필요합니다: sudo bash $0 $*"
    exit 1
fi

printf '%s' "$ENV_BODY" > "$ENV_PATH"
printf '%s' "$UNIT_BODY" > "$UNIT_PATH"
chmod 644 "$ENV_PATH" "$UNIT_PATH"
systemctl daemon-reload

echo "✓ 설치 완료"
echo "  유닛     : $UNIT_PATH"
echo "  환경설정 : $ENV_PATH   (TM_ROBOT_ID=${ROBOT_ID:-<미지정>})"
echo "  실행 사용자: $RUN_USER"
echo ""
echo "자동 시작 켜기 : sudo bash $WS/deploy/webgui-enable.sh"
echo "자동 시작 끄기 : sudo bash $WS/deploy/webgui-disable.sh"
echo "상태 보기      : bash $WS/deploy/webgui-status.sh"
