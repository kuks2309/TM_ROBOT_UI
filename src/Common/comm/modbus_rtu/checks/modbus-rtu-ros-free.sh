#!/usr/bin/env bash
# ⟦CI:modbus-rtu-ros-free⟧ — Comm 계층 ROS-free 강제 (modbus-tcp-ros-free.sh 와 동일 구조, 단계③ Task 5).
# modbus_rtu 소스·헤더에 rclcpp/tc_msgs/pio_hal include 유입 시 차단(common 은 서브시스템에 역의존 금지).
set -u
PKG_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCAN_DIRS=("$PKG_DIR/include" "$PKG_DIR/src" "$PKG_DIR/test" "$PKG_DIR/sim" "$PKG_DIR/tools")
HITS=$(grep -rEln '^[[:space:]]*#[[:space:]]*include[[:space:]]*[<"](rclcpp|tc_msgs|pio_hal)' \
  "${SCAN_DIRS[@]}" 2>/dev/null)
if [ -n "$HITS" ]; then
  echo "❌ modbus-rtu-ros-free: 금지 include 발견:"; echo "$HITS"; exit 1
fi

# 0건 스캔은 "깨끗함" 이 아니라 "대상을 못 찾음" 이다 — gripper-io-single-master.sh 선례와 동일하게
# 경로가 어긋난 채 초록이 되는 것을 막는다(최종 리뷰 I8).
scanned=$(find "${SCAN_DIRS[@]}" -type f \( -name '*.cpp' -o -name '*.hpp' -o -name '*.h' -o -name '*.cc' \
                                          -o -name '*.cxx' -o -name '*.hxx' \) 2>/dev/null | wc -l)
MIN_SCANNED=5
if [ "$scanned" -lt "$MIN_SCANNED" ]; then
  echo "❌ modbus-rtu-ros-free: 검사 대상 ${scanned} 파일 — 하한 ${MIN_SCANNED} 미달(경로 오류 의심: $PKG_DIR)"
  exit 1
fi

echo "✅ modbus-rtu-ros-free: rclcpp·tc_msgs·pio_hal include 0 (검사 대상 ${scanned} 파일)"
exit 0
