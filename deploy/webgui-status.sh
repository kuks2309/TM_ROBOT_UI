#!/usr/bin/env bash
# 웹 GUI 상태 한눈에 — 설치·자동시작·실행·포트·화면 유무.
# 권한이 없어도 읽기만 하므로 sudo 없이 돈다.
set -u
WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT="tm-webgui.service"

echo "=== tm-webgui 상태 ==="
if [ -f "/etc/systemd/system/$UNIT" ]; then
    echo "  유닛 설치   : 있음 (/etc/systemd/system/$UNIT)"
    echo "  자동 시작   : $(systemctl is-enabled "$UNIT" 2>/dev/null || echo 'disabled')"
    echo "  실행 상태   : $(systemctl is-active "$UNIT" 2>/dev/null || echo 'inactive')"
else
    echo "  유닛 설치   : ***없음*** — sudo bash deploy/webgui-install.sh"
fi

[ -f "/etc/default/tm-webgui" ] && {
    echo "  환경설정    : /etc/default/tm-webgui"
    sed 's/^/     /' /etc/default/tm-webgui | grep -v '^     #' | grep -v '^     $'
}

echo "  워크스페이스: $WS"
[ -f "$WS/install/setup.bash" ] && echo "  colcon 빌드 : 있음" || echo "  colcon 빌드 : ***없음*** — bash deploy/build.sh"
[ -f "$WS/webgui/dist/index.html" ] \
    && echo "  웹 GUI dist : 있음 ($(du -sh "$WS/webgui/dist" | cut -f1))" \
    || echo "  웹 GUI dist : ***없음*** — bash deploy/build.sh --web-only"

echo "  포트 8000   : $(ss -ltn 2>/dev/null | grep -q ':8000' && echo '열림' || echo '닫힘')  (웹 GUI)"
echo "  포트 9090   : $(ss -ltn 2>/dev/null | grep -q ':9090' && echo '열림' || echo '닫힘')  (rosbridge)"

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[ -n "$IP" ] && echo "  접속 주소   : http://$IP:8000"
echo ""
echo "로그: journalctl -u $UNIT -n 50 --no-pager"
