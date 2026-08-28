import time
from rclpy.node import Node
from typing import Optional, Tuple, Callable

from .tm_robot_script_motion import TmRobotScriptMotion
from .tm_robot_ros2_motion import TmRobotRos2Motion


class LandmarkAlignService:
    VISION_BASE_NAME = "vision_TM_Landmark_detection"

    def __init__(self, ros_node: Node = None, log_callback: Callable = None, gv_manager=None):
        self.ros_node = ros_node
        self._log_callback = log_callback
        self.gv_manager = gv_manager

        gateway = getattr(ros_node, 'motion_gateway', None)
        self.script_motion = (TmRobotScriptMotion(gv_manager, log_callback, gateway=gateway)
                              if gv_manager else None)
        self.ros2_motion = TmRobotRos2Motion(ros_node, log_callback) if ros_node else None

    def _log(self, message: str):
        if self._log_callback:
            self._log_callback(message)
        elif self.ros_node:
            self.ros_node.get_logger().info(message)

    def change_to_vision_base(self) -> Tuple[bool, str]:
        if not self.script_motion:
            return False, "Script Motion 서비스가 없습니다"

        return self.script_motion.change_base(self.VISION_BASE_NAME)

    def change_to_robot_base(self) -> Tuple[bool, str]:
        if not self.script_motion:
            return False, "Script Motion 서비스가 없습니다"

        return self.script_motion.change_base("RobotBase")

    def change_coordinate_system(self, base_name: str, align_pose: bool = False,
                                  current_tcp: list = None, velocity: float = 50.0) -> Tuple[bool, str]:
        if not self.script_motion:
            return False, "Script Motion 서비스가 없습니다"

        success, msg = self.script_motion.change_base(base_name)
        if not success:
            return False, msg

        if align_pose and current_tcp and len(current_tcp) >= 6:
            time.sleep(0.1)

            target_rx, target_ry, target_rz = self._get_target_pose_for_base(base_name)
            if target_rx is None:
                return True, f"좌표계 변경 완료: {base_name} (자세 정보 없음)"

            if self.ros2_motion:
                import math
                positions = [
                    current_tcp[0] / 1000.0,
                    current_tcp[1] / 1000.0,
                    current_tcp[2] / 1000.0,
                    target_rx * math.pi / 180.0,
                    target_ry * math.pi / 180.0,
                    target_rz * math.pi / 180.0
                ]
                success, msg = self.ros2_motion.move_line_tcp(
                    positions, velocity=velocity / 1000.0, acc_time=0.2
                )
                self._log(f"자세 정렬: Rx={target_rx:.2f}, Ry={target_ry:.2f}, Rz={target_rz:.2f}")

                if success:
                    return True, f"좌표계 변경 및 자세 정렬 완료: {base_name}"
                else:
                    return False, f"자세 정렬 실패: {msg}"

        return True, f"좌표계 변경 완료: {base_name}"

    def _get_target_pose_for_base(self, base_name: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        if base_name == "RobotBase":
            return 180.0, 0.0, 180.0

        elif base_name.startswith("vision_") and self.gv_manager:
            var_name = "g_TM_Landmark" if "Landmark" in base_name else "g_TM_Jig"

            success, value = self.gv_manager.read_variable(var_name)
            if success and value:
                try:
                    values = value.strip('{}').split(',')
                    if len(values) >= 6:
                        rx = float(values[3].strip())
                        ry = float(values[4].strip())
                        rz = float(values[5].strip())
                        return rx, ry, rz
                except (ValueError, IndexError) as e:
                    self._log(f"자세 파싱 실패: {e}")

        return None, None, None

    def move_to_landmark_center(self, z_distance: float, velocity: float = 100.0) -> Tuple[bool, str]:
        if not self.script_motion:
            return False, "Script Motion 서비스가 없습니다"

        success, msg = self.script_motion.line_cpp(
            x=0, y=0, z=z_distance,
            rx=180, ry=0, rz=180,
            velocity_mm=velocity, acc_time_ms=200
        )

        if success:
            return True, f"랜드마크 중심 정렬 완료: Z={z_distance}mm"
        else:
            return False, f"Line CPP 실패: {msg}"

    def align_to_landmark(
        self,
        z_distance: float = 100.0,
        velocity: float = 100.0,
        wait_time: float = 0.5
    ) -> Tuple[bool, str]:
        if not self.script_motion:
            return False, "Script Motion 서비스가 없습니다"

        self._log("TM Landmark 정렬 시작...")

        success, msg = self.change_to_vision_base()
        if not success:
            return False, msg
        self._log(msg)

        time.sleep(0.1)
        success, msg = self.move_to_landmark_center(z_distance, velocity)
        if not success:
            return False, msg
        self._log(msg)

        time.sleep(wait_time)

        result_msg = f"Landmark 정렬 완료 (X=0, Y=0, Z={z_distance}mm)"
        self._log(result_msg)
        return True, result_msg
