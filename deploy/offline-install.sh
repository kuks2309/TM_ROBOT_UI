#!/usr/bin/env bash
# 인터넷 없는 타깃에 웹 GUI 파이썬 의존성을 설치한다.
#
# 동봉한 deploy/offline/wheels 의 휠만 쓴다 (`--no-index`) — 네트워크를 타지 않는다는
# 것을 pip 에 명시적으로 강제한다. 휠은 **x86_64 / CPython 3.10** 용으로 받아 뒀다
# (타깃 Advantech PC 기준, MK4 워크스페이스의 ELF 로 확인).
#
# 사용:
#   bash deploy/offline-install.sh            # 사용자 영역(--user)에 설치
#   sudo bash deploy/offline-install.sh --system
set -u

WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WHEELS="$WS/deploy/offline/wheels"
# 기본은 **워크스페이스 안(vendor/pylibs)** 이다.
#   · `--user` 로 깔면 ~/.local 에 가는데, run 이 PYTHONNOUSERSITE=1 로 띄우므로
#     노드에서는 **안 보인다** (2026-08-27 팹에서 실제로 이것 때문에 막혔다).
#   · vendor/pylibs 는 launch 가 PYTHONPATH 로 직접 얹으므로 그 함정을 안 탄다.
VENDOR="$WS/vendor/pylibs"
TARGET_ARGS=(--target "$VENDOR" --upgrade)
MODE="vendor"
case "${1:-}" in
    --user)   TARGET_ARGS=(--user);  MODE="사용자(~/.local)" ;;
    --system) TARGET_ARGS=();        MODE="시스템 전역" ;;
esac

if [ ! -d "$WHEELS" ]; then
    echo "✗ 휠 디렉터리가 없다: $WHEELS"
    exit 1
fi
COUNT=$(find "$WHEELS" -name '*.whl' | wc -l)
if [ "$COUNT" = "0" ]; then
    echo "✗ $WHEELS 에 휠이 없다"
    exit 1
fi

echo "=== 오프라인 설치 ==="
echo "  휠      : $COUNT 개 ($WHEELS)"
echo "  아키텍처: $(uname -m)  (휠은 x86_64 용)"
echo "  설치 위치: $MODE"
echo ""

if [ "$(uname -m)" != "x86_64" ]; then
    echo "⚠ 이 기계는 x86_64 가 아니다. 동봉 휠이 맞지 않을 수 있다."
fi

# --no-index: 인터넷을 아예 보지 않는다. --find-links: 동봉 휠만 본다.
if python3 -m pip install "${TARGET_ARGS[@]}" --no-index --find-links "$WHEELS" \
        fastapi uvicorn flask waitress; then
    echo ""
    echo "✓ 설치 완료 — 확인:"
    # 노드와 같은 조건(PYTHONNOUSERSITE=1)으로 확인한다.
    PYTHONNOUSERSITE=1 PYTHONPATH="$VENDOR:${PYTHONPATH:-}" \
        python3 -c "import fastapi,uvicorn,flask,waitress;print('   flask',flask.__version__,'/ waitress OK / fastapi',fastapi.__version__)"
else
    echo ""
    echo "✗ 설치 실패. 휠 목록:"
    ls "$WHEELS"
    exit 1
fi

echo ""
echo "다음: bash deploy/check-deps.sh  →  bash deploy/build.sh"
