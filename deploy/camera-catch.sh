#!/usr/bin/env bash
# 로봇(TMflow)을 못 만지는 상황에서, PC 쪽만으로 카메라 이미지를 받아내는 도구.
#
# 원리
#   로봇은 TMflow 비전 잡의 «외부 감지 URL» 로 사진을 HTTP POST 한다. 그 URL 이
#   이 PC 를 안 가리키면 아무리 기다려도 안 온다. 로봇을 못 만지면 URL 을 못 바꾼다.
#   → 대신 **그 IP 를 이 PC 가 가져오면** 된다.
#
#   그 IP 가 무엇인지도 PC 에서 알 수 있다. 로봇이 없는 IP 로 보내려 하면 먼저
#   **ARP 로 «누가 그 IP 냐» 고 브로드캐스트**하는데, 브로드캐스트는 같은 망의
#   모든 NIC 에 도달하므로 우리가 그대로 볼 수 있다.
#
# 사용
#   bash deploy/camera-catch.sh watch          # 로봇이 어느 IP 를 찾는지 엿본다
#   bash deploy/camera-catch.sh status         # 현재 IP·포트·브리지 상태
#   sudo bash deploy/camera-catch.sh claim 169.254.183.100
#   sudo bash deploy/camera-catch.sh unclaim 169.254.183.100
#   bash deploy/camera-catch.sh selftest       # PC 수신 경로만 따로 검사
set -u

WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${TM_CAMERA_PORT:-6189}"
LOG=/tmp/camera-catch.log

# 문서(issues_and_fixes.md:268~)에 기록된, 예전에 외부 감지 URL 로 쓰던 주소.
# 로봇 설정이 그대로면 지금도 이 IP 로 쏘고 있을 가능성이 크다.
KNOWN_TARGETS=(169.254.183.100)

usage() { sed -n '2,26p' "$0"; }

pick_iface() {
    # 기본 경로가 나가는 NIC. claim 할 때 어디에 붙일지 정한다.
    ip route show default 2>/dev/null | awk '{print $5; exit}'
}

cmd_status() {
    echo "=== 이 PC 의 IP ==="
    hostname -I | tr ' ' '\n' | grep -v '^$' | sed 's/^/  /'
    echo ""
    echo "=== NIC 별 주소 ==="
    ip -4 -o addr show | awk '{printf "  %-10s %s\n", $2, $4}'
    echo ""
    echo "=== :$PORT 를 누가 잡고 있나 ==="
    ss -ltnp 2>/dev/null | grep ":$PORT" || echo "  아무도 안 잡음 ← 브리지가 안 떴다"
    echo ""
    echo "=== 카메라 브리지 프로세스 ==="
    pgrep -af tm_camera_bridge || echo "  없음"
    echo ""
    echo "=== 방화벽 ==="
    (sudo -n ufw status 2>/dev/null || echo "  (sudo 없이 확인 불가 — 보통 inactive)") | head -3
    echo ""
    echo "=== 문서에 기록된 옛 외부 감지 대상 ==="
    for ip in "${KNOWN_TARGETS[@]}"; do
        if ip -4 -o addr show | grep -q "$ip"; then
            echo "  $ip  ← 이미 이 PC 가 갖고 있음 ✓"
        else
            echo "  $ip  ← 이 PC 에 없음. 필요하면: sudo bash $0 claim $ip"
        fi
    done
}

cmd_watch() {
    if ! command -v tcpdump >/dev/null 2>&1; then
        echo "✗ tcpdump 가 없습니다. 대신 이렇게 보세요:"
        echo "    watch -n1 'ip neigh; ss -tan | grep $PORT'"
        exit 1
    fi
    echo "=== 엿보기 시작 — 이 상태로 UI 에서 Image Capture 를 누르세요 ==="
    echo "  기록: $LOG   (멈추려면 Ctrl+C)"
    echo ""
    echo "  [해석]"
    echo "   · 'ARP, Request who-has X.X.X.X'  → 로봇이 그 IP 를 찾는 중."
    echo "                                       그 IP 가 우리 것이 아니면 그게 원인."
    echo "                                       → sudo bash $0 claim X.X.X.X"
    echo "   · 'IP  로봇 > 우리:$PORT'          → 우리한테 오고 있음. 브리지 문제."
    echo "   · 아무것도 없음                    → 로봇이 이 망으로 아무것도 안 보냄."
    echo ""
    sudo tcpdump -i any -n -l "arp or tcp port $PORT" 2>&1 | tee "$LOG"
}

cmd_claim() {
    local ip="${1:-}"
    [ -z "$ip" ] && { echo "✗ IP 를 주세요: sudo bash $0 claim 169.254.183.100"; exit 1; }
    [ "$(id -u)" != "0" ] && { echo "✗ root 권한 필요: sudo bash $0 claim $ip"; exit 1; }

    local iface prefix
    iface="${TM_IFACE:-$(pick_iface)}"
    [ -z "$iface" ] && { echo "✗ NIC 을 못 찾았습니다. TM_IFACE=eth0 처럼 지정하세요."; exit 1; }
    case "$ip" in
        169.254.*) prefix=16 ;;
        *)         prefix=24 ;;
    esac

    if ip -4 -o addr show | grep -q "$ip"; then
        echo "· 이미 갖고 있습니다: $ip"
        exit 0
    fi

    echo "⚠️  같은 망에 그 IP 를 쓰는 기계가 **살아 있으면 충돌**합니다."
    echo "    문서상 $ip 는 코봇(aMAP) 의 eno1 주소였습니다."
    echo "    코봇이 이 망에 붙어 있지 않은 것을 확인하고 진행하세요."
    echo ""
    if ping -c1 -W1 "$ip" >/dev/null 2>&1; then
        echo "✗ $ip 가 **이미 응답합니다** — 누군가 쓰고 있습니다. 중단합니다."
        echo "  그 기계를 내리거나 다른 방법을 쓰세요."
        exit 1
    fi
    echo "· ping 무응답 확인 — 비어 있는 주소로 판단"

    if ip addr add "$ip/$prefix" dev "$iface"; then
        echo "✓ $ip/$prefix 를 $iface 에 추가했습니다"
        echo "  되돌리기: sudo bash $0 unclaim $ip"
        echo ""
        echo "  이제 UI 에서 Image Capture 를 눌러 보세요."
        echo "  ./run 콘솔에 [카메라] POST 수신 이 뜨면 성공입니다."
        echo ""
        echo "  ⚠️ 재부팅하면 사라집니다(임시). 계속 쓰려면 netplan 에 고정하세요."
    else
        echo "✗ 추가 실패"
        exit 1
    fi
}

cmd_unclaim() {
    local ip="${1:-}"
    [ -z "$ip" ] && { echo "✗ IP 를 주세요"; exit 1; }
    [ "$(id -u)" != "0" ] && { echo "✗ root 권한 필요: sudo bash $0 unclaim $ip"; exit 1; }
    local line iface prefix
    line="$(ip -4 -o addr show | grep "$ip" | head -1)"
    [ -z "$line" ] && { echo "· 이 PC 에 $ip 가 없습니다"; exit 0; }
    iface="$(echo "$line" | awk '{print $2}')"
    prefix="$(echo "$line" | awk '{print $4}' | cut -d/ -f2)"
    ip addr del "$ip/$prefix" dev "$iface" && echo "✓ $ip 제거 ($iface)"
}

cmd_selftest() {
    echo "=== PC 수신 경로만 검사 (로봇 없이) ==="
    local img=/tmp/tm_selftest.jpg
    python3 -c "import cv2,numpy as np; cv2.imwrite('$img', np.full((480,640,3),128,'uint8'))" \
        || { echo "✗ 테스트 이미지 생성 실패 (opencv 확인)"; exit 1; }
    ls -l "$img"
    echo ""
    echo "--- POST /api/DET ---"
    curl -s -o /dev/null -w "  HTTP %{http_code}\n" -F "image=@$img" \
        "http://localhost:$PORT/api/DET"
    echo "--- POST / (catch-all 확인) ---"
    curl -s -o /dev/null -w "  HTTP %{http_code}\n" -F "image=@$img" \
        "http://localhost:$PORT/"
    echo ""
    echo "  ./run 콘솔에 아래가 뜨면 **PC 는 정상**입니다:"
    echo "    [카메라] POST 수신 127.0.0.1 bytes=..."
    echo "    [카메라] /techman_image 발행 640x480 bgr8"
    echo ""
    echo "  토픽으로 직접 보려면 다른 창에서:"
    echo "    ros2 topic echo /techman_image --once"
}

case "${1:-}" in
    status)  cmd_status ;;
    watch)   cmd_watch ;;
    claim)   shift; cmd_claim "${1:-}" ;;
    unclaim) shift; cmd_unclaim "${1:-}" ;;
    selftest) cmd_selftest ;;
    *) usage ;;
esac
