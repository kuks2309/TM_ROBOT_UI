#!/usr/bin/env bash
# ⟦CI:modbus-rtu-ros-free⟧ — Comm 계층 ROS-free 강제 (modbus-tcp-ros-free.sh 와 동일 구조, 단계③ Task 5).
# modbus_rtu 소스·헤더에 rclcpp/tc_msgs/pio_hal include 유입 시 차단(common 은 서브시스템에 역의존 금지).
set -u
PKG_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HITS=$(grep -rEln '^[[:space:]]*#[[:space:]]*include[[:space:]]*[<"](rclcpp|tc_msgs|pio_hal)' \
  "$PKG_DIR/include" "$PKG_DIR/src" "$PKG_DIR/test" 2>/dev/null)
if [ -n "$HITS" ]; then
  echo "❌ modbus-rtu-ros-free: 금지 include 발견:"; echo "$HITS"; exit 1
fi
echo "✅ modbus-rtu-ros-free: rclcpp·tc_msgs·pio_hal include 0"
exit 0
