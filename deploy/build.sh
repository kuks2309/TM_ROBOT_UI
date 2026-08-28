#!/usr/bin/env bash
# tm-robot-uni 전체 빌드 — ROS2 워크스페이스 + 웹 GUI 프런트.
#
# 인터넷 없는 공장에서 그대로 도는 것을 전제로 한다:
#   · 프런트는 webgui/node_modules 를 이미 들고 있어 npm 이 네트워크를 타지 않는다
#   · 빌드 결과 webgui/dist 는 브리지가 직접 서빙하므로 CDN 도 필요 없다
#
# 사용:
#   bash deploy/build.sh                # 전체 (ROS2 + 프런트) — 배포용 일반 빌드
#   bash deploy/build.sh --symlink      # 개발용 심링크 빌드 (아래 주의)
#   bash deploy/build.sh --ros-only     # ROS2 만
#   bash deploy/build.sh --web-only     # 프런트 만
#   bash deploy/build.sh --packages tm_task_manager tm_web_bridge
#
# ⚠️ 기본이 **일반 빌드**인 이유 (2026-08-27 실측):
#    `--symlink-install` 로 빌드하면 `import tm_task_manager` 가
#    `build/tm_task_manager/tm_task_manager` 에서 잡힌다. 소스가 아니라 빌드
#    디렉터리다. `paths.py` 가 `resolve()` 로 심링크를 풀어 방어하고 있지만,
#    이 경로로 새 파일을 추가하면 다시 빌드하기 전까지 보이지 않고,
#    `checks/install_sync.sh` 도 «설치본 없음» 으로 검사 자체를 못 한다.
#    현장 배포는 install/ 이 자립해야 하므로 일반 빌드를 기본으로 둔다.
#    개발 중 반복 수정에는 --symlink 가 편하다.
#
# 종료코드: 0 성공 / 1 실패
set -u

WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROS_SETUP="${ROS_SETUP:-/opt/ros/humble/setup.bash}"

DO_ROS=1
DO_WEB=1
SYMLINK=0
PACKAGES=()

while [ $# -gt 0 ]; do
    case "$1" in
        --ros-only) DO_WEB=0; shift ;;
        --web-only) DO_ROS=0; shift ;;
        --symlink) SYMLINK=1; shift ;;
        --packages) shift; while [ $# -gt 0 ] && [[ "$1" != --* ]]; do PACKAGES+=("$1"); shift; done ;;
        -h|--help) sed -n '2,26p' "$0"; exit 0 ;;
        *) echo "알 수 없는 인자: $1"; exit 1 ;;
    esac
done

say() { echo ""; echo "=== $* ==="; }

# ---------------------------------------------------------------- 사전 확인
say "환경 확인"
if [ ! -f "$ROS_SETUP" ]; then
    echo "✗ ROS2 setup 을 찾지 못했습니다: $ROS_SETUP"
    echo "  다른 배포판이면 ROS_SETUP=/opt/ros/<distro>/setup.bash 로 지정하십시오."
    exit 1
fi
echo "  워크스페이스 : $WS"
echo "  ROS setup    : $ROS_SETUP"

# ---------------------------------------------------------------- ROS2 빌드
if [ "$DO_ROS" = "1" ]; then
    say "ROS2 워크스페이스 빌드 (colcon)"
    # ⚠️ ROS 의 setup.bash 는 미정의 변수를 참조한다. `set -u` 인 채로 소싱하면
    #    스크립트가 그 자리에서 조용히 죽는다(2026-08-27 실측: 로그 첫 줄에서 끊김).
    # shellcheck disable=SC1090
    set +u
    source "$ROS_SETUP"
    set -u
    cd "$WS" || exit 1

    ARGS=(--event-handlers console_direct+)
    if [ "$SYMLINK" = "1" ]; then
        ARGS+=(--symlink-install)
        echo "  모드: 심링크 빌드 (개발용)"
    else
        echo "  모드: 일반 빌드 (배포용)"
    fi
    if [ "${#PACKAGES[@]}" -gt 0 ]; then
        ARGS+=(--packages-select "${PACKAGES[@]}")
        echo "  대상 패키지: ${PACKAGES[*]}"
    fi

    if ! colcon build "${ARGS[@]}"; then
        echo "✗ colcon build 실패"
        exit 1
    fi
    echo "✓ colcon build 완료"

    # 설치본과 소스가 어긋나면 «위젯은 보이는데 버튼이 죽은» 상태가 된다(2026-08-22 사고).
    # 심링크 빌드에는 install/.../site-packages 사본 자체가 없어 검사가 성립하지 않는다.
    if [ -f "$WS/src/TM_Robot_Task_Manager/checks/install_sync.sh" ]; then
        if [ "$SYMLINK" = "1" ]; then
            say "설치본 ↔ 소스 일치 검사 — 건너뜀"
            echo "  심링크 빌드는 install/ 에 .py 사본을 만들지 않아 이 검사가 성립하지 않습니다."
            echo "  배포 전에는 --symlink 없이 한 번 빌드해 검사를 통과시키십시오."
        else
            say "설치본 ↔ 소스 일치 검사"
            bash "$WS/src/TM_Robot_Task_Manager/checks/install_sync.sh" "$WS" || {
                echo "✗ 설치본이 소스와 다릅니다 — 위 목록을 확인하십시오"
                exit 1
            }
            echo "✓ 설치본 일치"
        fi
    fi
fi

# ---------------------------------------------------------------- 프런트 빌드
if [ "$DO_WEB" = "1" ]; then
    say "웹 GUI 프런트 빌드 (vite)"
    if [ ! -d "$WS/webgui" ]; then
        echo "✗ webgui 디렉터리가 없습니다: $WS/webgui"
        exit 1
    fi
    if ! command -v npm >/dev/null 2>&1; then
        echo "✗ npm 이 없습니다. 프런트를 다시 빌드하지 않을 것이라면 --ros-only 를 쓰십시오."
        exit 1
    fi
    if [ ! -d "$WS/webgui/node_modules" ]; then
        echo "✗ webgui/node_modules 가 없습니다."
        echo "  인터넷 없는 환경에서는 복원할 수 없습니다 — node_modules 를 통째로 가져오십시오."
        exit 1
    fi
    # node_modules 의 네이티브 바인딩이 이 기계 아키텍처와 맞는지 본다.
    # 2026-08-27: aarch64(코봇)에서 복사한 node_modules 를 x86_64 타깃에서 쓰다
    # `@rolldown/binding-linux-x64-gnu` 없음으로 빌드가 죽었다. dist 가 이미
    # 있으면 웹 GUI 는 그대로 동작하므로, 여기서 멈추지 말고 건너뛴다.
    NATIVE_OK=1
    case "$(uname -m)" in
        x86_64) ls "$WS/webgui/node_modules/@rolldown/" 2>/dev/null | grep -q 'x64' || NATIVE_OK=0 ;;
        aarch64) ls "$WS/webgui/node_modules/@rolldown/" 2>/dev/null | grep -q 'arm64' || NATIVE_OK=0 ;;
    esac
    if [ "$NATIVE_OK" = "0" ]; then
        echo "⚠ node_modules 의 네이티브 바인딩이 이 기계($(uname -m))와 맞지 않습니다."
        if [ -f "$WS/webgui/dist/index.html" ]; then
            echo "  이미 빌드된 dist 가 있어 웹 GUI 는 그대로 동작합니다 — 프런트 빌드를 건너뜁니다."
            echo "  다시 빌드해야 하면 인터넷 있는 곳에서: cd webgui && rm -rf node_modules package-lock.json && npm i"
            DO_WEB=0
        else
            echo "✗ dist 도 없습니다 — 웹 화면이 안 뜹니다."
            exit 1
        fi
    fi
fi

if [ "$DO_WEB" = "1" ]; then
    cd "$WS/webgui" || exit 1
    # `npm run build`(tsc -b && vite build)는 node_modules 만 읽고 네트워크를 타지 않는다.
    # 위에서 node_modules 존재를 먼저 확인했으므로 여기서 install 을 부르지 않는다 —
    # 인터넷 없는 현장에서 npm install 이 끼면 그 자리에서 멈춘다.
    if ! npm run build; then
        echo "✗ 프런트 빌드 실패"
        exit 1
    fi
    if [ ! -f "$WS/webgui/dist/index.html" ]; then
        echo "✗ dist/index.html 이 생기지 않았습니다"
        exit 1
    fi
    echo "✓ 프런트 빌드 완료: $WS/webgui/dist ($(du -sh "$WS/webgui/dist" | cut -f1))"
fi

say "빌드 끝"
echo "다음:"
echo "  source $WS/install/setup.bash"
echo "  ros2 launch tm_web_bridge web_bridge.launch.py     # 웹 GUI + rosbridge"
echo "  ros2 launch tm_task_manager task_manager.launch.py # PyQt"
echo ""
echo "자동 부팅 등록:  bash $WS/deploy/webgui-install.sh"
