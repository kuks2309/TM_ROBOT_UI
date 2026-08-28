#!/usr/bin/env bash
# 웹 GUI 자동 부팅 **켜기** — 지금 바로 시작하고, 다음 부팅부터 자동으로 뜬다.
#
# 사용: sudo bash deploy/webgui-enable.sh [--no-start]
set -u
UNIT="tm-webgui.service"
NO_START=0
[ "${1:-}" = "--no-start" ] && NO_START=1

if [ ! -f "/etc/systemd/system/$UNIT" ]; then
    echo "✗ 유닛이 설치돼 있지 않습니다. 먼저: sudo bash deploy/webgui-install.sh"
    exit 1
fi
if [ "$(id -u)" != "0" ]; then
    echo "✗ root 권한이 필요합니다: sudo bash $0"
    exit 1
fi

systemctl daemon-reload
systemctl enable "$UNIT" || exit 1
echo "✓ 자동 부팅 켜짐"

if [ "$NO_START" = "0" ]; then
    systemctl restart "$UNIT" || exit 1
    sleep 2
    systemctl is-active --quiet "$UNIT" && echo "✓ 지금 실행 중" || {
        echo "✗ 시작 실패 — 로그: journalctl -u $UNIT -n 50 --no-pager"
        exit 1
    }
    echo "  접속: http://$(hostname -I | awk '{print $1}'):8000"
fi
