import time
import rclpy
from rclpy.node import Node
from typing import Tuple, List, Optional, Callable
from tm_msgs.srv import SetPositions


class TmRobotRos2Motion:
    PTP_J = SetPositions.Request.PTP_J
    PTP_T = SetPositions.Request.PTP_T
    LINE_T = SetPositions.Request.LINE_T

    def __init__(self, ros_node: Node, log_callback: Callable[[str], None] = None):
        self.ros_node = ros_node
        self._log_callback = log_callback

    def _log(self, message: str):
        if self._log_callback:
            self._log_callback(message)
        elif self.ros_node:
            self.ros_node.get_logger().info(message)

    def move_ptp_joint(
        self,
        joint_positions: List[float],
        velocity: float = 10.0,
        acc_time: float = 0.2,
        blend_percentage: int = 0,
        fine_goal: bool = False
    ) -> Tuple[bool, str]:
        if len(joint_positions) != 6:
            return False, "Joint 위치는 6개 값이 필요합니다"

        self._log(f"PTP_J 이동: {[f'{j:.3f}' for j in joint_positions]}, V={velocity}%")
        return self._call_set_positions(
            self.PTP_J, joint_positions, velocity, acc_time, blend_percentage, fine_goal
        )

    def move_ptp_tcp(
        self,
        tcp_position: List[float],
        velocity: float = 10.0,
        acc_time: float = 0.2,
        blend_percentage: int = 0,
        fine_goal: bool = False
    ) -> Tuple[bool, str]:
        if len(tcp_position) != 6:
            return False, "TCP 위치는 6개 값이 필요합니다"

        self._log(f"PTP_T 이동: X={tcp_position[0]*1000:.1f}mm, Y={tcp_position[1]*1000:.1f}mm, Z={tcp_position[2]*1000:.1f}mm, V={velocity}%")
        return self._call_set_positions(
            self.PTP_T, tcp_position, velocity, acc_time, blend_percentage, fine_goal
        )

    def move_line_tcp(
        self,
        tcp_position: List[float],
        velocity: float = 10.0,
        acc_time: float = 0.2,
        blend_percentage: int = 0,
        fine_goal: bool = False
    ) -> Tuple[bool, str]:
        if len(tcp_position) != 6:
            return False, "TCP 위치는 6개 값이 필요합니다"

        self._log(f"LINE_T 이동: X={tcp_position[0]*1000:.1f}mm, Y={tcp_position[1]*1000:.1f}mm, Z={tcp_position[2]*1000:.1f}mm, V={velocity}%")
        return self._call_set_positions(
            self.LINE_T, tcp_position, velocity, acc_time, blend_percentage, fine_goal
        )

    def _call_set_positions(
        self,
        motion_type: int,
        positions: List[float],
        velocity: float,
        acc_time: float,
        blend_percentage: int = 0,
        fine_goal: bool = False
    ) -> Tuple[bool, str]:
        if not self.ros_node:
            return False, "ROS2 노드가 없습니다"

        if hasattr(self.ros_node, '_call_set_positions'):
            return self.ros_node._call_set_positions(
                motion_type, positions, velocity, acc_time, blend_percentage, fine_goal
            )

        return False, "ROS2 노드에 _call_set_positions 메서드가 없습니다"
