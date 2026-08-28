#!/usr/bin/env bash
# tm_task_manager 설치본(install/)이 소스(src/)와 일치하는지 검사한다.
#
# 존재 이유: paths.py 가 설치본에서 실행될 때도 PACKAGE_ROOT 를 소스 트리로 역산하므로
# .ui 는 소스에서 즉시 반영되지만 .py 는 install/ 사본이 쓰인다. 이 비대칭 때문에
# "위젯은 새로 보이는데 버튼이 죽어 있는" 상태가 만들어진다(2026-08-22 실제 사고).
# 소스만 배포하고 colcon build 를 건너뛰면 이 검사가 잡아낸다.
#
# 사용: bash checks/install_sync.sh [워크스페이스_루트]
# 종료코드: 0 = 일치, 1 = 불일치 또는 설치본 없음

set -u

WS="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
SRC="$WS/src/TM_Robot_Task_Manager"
LIB="$WS/install/tm_task_manager/lib/python3.10/site-packages/tm_task_manager"
SHARE="$WS/install/tm_task_manager/share/tm_task_manager"

if [ ! -d "$LIB" ]; then
    echo "✗ 설치본 없음: $LIB — colcon build --packages-select tm_task_manager 필요"
    exit 1
fi

fail=0
missing=0
compared=0

compare_tree() {
    local src_root="$1" dst_root="$2" pattern="$3"
    while IFS= read -r -d '' src_file; do
        local rel="${src_file#$src_root/}"
        local dst_file="$dst_root/$rel"

        if [ ! -f "$dst_file" ]; then
            echo "✗ 설치본에 없음: $rel"
            missing=$((missing + 1))
            continue
        fi

        compared=$((compared + 1))
        if ! cmp -s "$src_file" "$dst_file"; then
            echo "✗ 내용 불일치: $rel"
            fail=$((fail + 1))
        fi
    done < <(find "$src_root" -name "$pattern" -not -path '*/__pycache__/*' -print0)
}

compare_tree "$SRC/tm_task_manager" "$LIB" '*.py'
compare_tree "$SRC/ui" "$SHARE/ui" '*.ui'

echo "--- 비교 $compared 건 | 불일치 $fail | 설치누락 $missing"

if [ $((fail + missing)) -ne 0 ]; then
    echo "✗ 설치본이 소스와 다릅니다 — colcon build --packages-select tm_task_manager 후 GUI 재기동"
    exit 1
fi

echo "✓ 설치본이 소스와 일치"
exit 0
