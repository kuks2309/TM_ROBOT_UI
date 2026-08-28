#!/usr/bin/env bash
# ⟦CI:gripper-io-single-master⟧ — 그리퍼가 스테이션에 직접 접근하면 fail.
#
# 스테이션의 유일 쓰기 마스터는 remote_io_ros 노드다(ADR-008 Q7 · ADR-001(remote_io)).
# 그리퍼는 그 노드의 서비스 클라이언트일 뿐이므로, 스택 어디에도 Modbus·소켓 심볼이나
# 스테이션 포트 직접 참조가 있으면 안 된다. ROS 결선은 gripper_ros(조립층)에만 허용한다.
set -u
STACK_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# 대소문자 무시로 검사한다(-i) — ModbusMaster.h · MODBUS/tcp.hpp 류 우회 차단.
BANNED_IO='(modbus|mbapclient|iremoteiostationport|remoteiostationport|remote_io_hal/|sys/socket\.h|netinet/in\.h|arpa/inet\.h|netdb\.h|sys/un\.h|boost/asio|asio\.hpp|::socket[[:space:]]*\(|[^a-z_]socket[[:space:]]*\()'
# ROS 결선이 허용되는 조립 패키지만 예외로 둔다 — 화이트리스트 방식이면 신규 패키지가 무검사로 샌다.
ROS_ASSEMBLY_PKGS="gripper_ros"
BANNED_ROS='^[[:space:]]*#[[:space:]]*include[[:space:]]*[<"](rclcpp|rclcpp_lifecycle|rclcpp_action|std_msgs|sensor_msgs|geometry_msgs|nav_msgs|tc_msgs|ament_)'

FAIL=0

SRC_GLOBS=(--include='*.cpp' --include='*.hpp' --include='*.h' --include='*.hh' --include='*.cc'
           --include='*.cxx' --include='*.hxx' --include='*.c' --include='*.py')
# 빌드 그래프도 접근 경로다 — 의존 선언이 쓰기 마스터 2개화의 첫 증상이다.
BUILD_GLOBS=(--include='CMakeLists.txt' --include='*.cmake' --include='package.xml')
BANNED_BUILD='(remote_io_hal|modbus_tcp|modbus_rtu)'

hits=$(grep -riEn "${SRC_GLOBS[@]}" "$BANNED_IO" "$STACK_DIR" 2>/dev/null)
if [ -n "$hits" ]; then
  echo "❌ gripper-io-single-master: 스테이션 직접 접근 심볼 발견"
  echo "$hits"
  FAIL=1
fi

build_hits=$(grep -riEn "${BUILD_GLOBS[@]}" "$BANNED_BUILD" "$STACK_DIR" 2>/dev/null)
if [ -n "$build_hits" ]; then
  echo "❌ gripper-io-single-master: 빌드 그래프에 스테이션·통신 패키지 의존 선언"
  echo "$build_hits"
  FAIL=1
fi

for pkg_dir in "$STACK_DIR"/*/; do
  pkg="$(basename "$pkg_dir")"
  case " $ROS_ASSEMBLY_PKGS " in *" $pkg "*) continue ;; esac
  ros_hits=$(grep -rEn "${SRC_GLOBS[@]}" "$BANNED_ROS" "$pkg_dir" 2>/dev/null)
  if [ -n "$ros_hits" ]; then
    echo "❌ gripper-io-single-master: ROS-free 계층에 ROS include ($pkg)"
    echo "$ros_hits"
    FAIL=1
  fi
done

scanned=$(find "$STACK_DIR" \( -name '*.cpp' -o -name '*.hpp' -o -name '*.h' -o -name '*.hh' -o -name '*.cc' \
                              -o -name '*.cxx' -o -name '*.hxx' -o -name '*.c' -o -name '*.py' \) | wc -l)
# 0건 스캔은 "깨끗함" 이 아니라 "대상을 못 찾음" 이다 — 경로가 어긋난 채 초록이 되는 것을 막는다.
# 하한은 env 로 낮출 수 없다 — 낮추면 "0건 스캔 = 초록" 구멍이 복원된다.
MIN_SCANNED=5
if [ "$scanned" -lt "$MIN_SCANNED" ]; then
  echo "❌ gripper-io-single-master: 검사 대상 ${scanned} 파일 — 하한 ${MIN_SCANNED} 미달(경로 오류 의심: $STACK_DIR)"
  FAIL=1
fi

if [ "$FAIL" -eq 0 ]; then
  echo "✅ gripper-io-single-master: 직접 접근 0건 (검사 대상 ${scanned} 파일)"
fi
exit "$FAIL"
