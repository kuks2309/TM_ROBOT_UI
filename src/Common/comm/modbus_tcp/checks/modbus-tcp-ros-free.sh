#!/usr/bin/env bash
# ⟦CI:modbus-tcp-ros-free⟧ — Comm 계층 ROS-free 강제 (리뷰 minor 반영 2026-07-31).
# modbus_tcp 소스·헤더에 rclcpp/tc_msgs/pio_hal include 유입 시 차단(common 은 서브시스템에 역의존 금지).
set -u
PKG_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HITS=$(grep -rEln '^[[:space:]]*#[[:space:]]*include[[:space:]]*[<"](rclcpp|tc_msgs|pio_hal)' \
  "$PKG_DIR/include" "$PKG_DIR/src" "$PKG_DIR/test" 2>/dev/null)
if [ -n "$HITS" ]; then
  echo "❌ modbus-tcp-ros-free: 금지 include 발견:"; echo "$HITS"; exit 1
fi
echo "✅ modbus-tcp-ros-free: rclcpp·tc_msgs·pio_hal include 0"
exit 0
