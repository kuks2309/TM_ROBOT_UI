#!/usr/bin/env bash
# 웹 GUI 자동 부팅 **끄기** — 지금 실행 중인 것도 멈춘다.
#
# 유닛 파일은 지우지 않는다. 되돌리려면 webgui-enable.sh 만 다시 부르면 된다.
# 사용: sudo bash deploy/webgui-disable.sh [--keep-running]
set -u
UNIT="tm-webgui.service"
KEEP=0
[ "${1:-}" = "--keep-running" ] && KEEP=1

if [ "$(id -u)" != "0" ]; then
    echo "✗ root 권한이 필요합니다: sudo bash $0"
    exit 1
fi
if [ ! -f "/etc/systemd/system/$UNIT" ]; then
    echo "· 유닛이 설치돼 있지 않습니다 — 할 일이 없습니다."
    exit 0
fi

systemctl disable "$UNIT" >/dev/null 2>&1
echo "✓ 자동 부팅 꺼짐 (유닛 파일은 남겨 둡니다)"

if [ "$KEEP" = "0" ]; then
    systemctl stop "$UNIT" >/dev/null 2>&1
    sleep 1
    systemctl is-active --quiet "$UNIT" && echo "⚠ 아직 실행 중입니다" || echo "✓ 정지됨"
fi
