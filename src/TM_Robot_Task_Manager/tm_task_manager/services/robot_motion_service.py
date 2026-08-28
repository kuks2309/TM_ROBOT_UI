import math
from typing import Optional, List, Tuple
from PyQt5.QtCore import QObject, pyqtSignal


TM_JOINT_NAMES = ('joint_1', 'joint_2', 'joint_3', 'joint_4', 'joint_5', 'joint_6')


def is_tm_joint_state(names, positions) -> bool:
    if positions is None or len(positions) < 6:
        return False
    if names:
        return tuple(names[:6]) == TM_JOINT_NAMES
    return len(positions) == 6


class RobotMotionService(QObject):
    joint_position_updated = pyqtSignal(list)
    tcp_pose_updated = pyqtSignal(list)
    motion_state_changed = pyqtSignal(bool)
    motion_completed = pyqtSignal(bool, str)

    def __init__(self):
        super().__init__()

        self._current_joint_position: Optional[List[float]] = None
        self._current_tcp_pose: Optional[List[float]] = None
        self._current_base_name: str = "RobotBase"

        self._robot_moving: bool = False
        self._target_position: Optional[List[float]] = None

        self._position_tolerance: float = 0.01
        self._velocity_tolerance: float = 0.01

        self._last_position_error: Optional[List[float]] = None
        self._last_rotation_error: Optional[List[float]] = None
        self._last_joint_error: Optional[List[float]] = None


    @property
    def current_joint_position(self) -> Optional[List[float]]:
        return self._current_joint_position

    @property
    def current_tcp_pose(self) -> Optional[List[float]]:
        return self._current_tcp_pose

    @property
    def current_base_name(self) -> str:
        return self._current_base_name

    @current_base_name.setter
    def current_base_name(self, value: str):
        self._current_base_name = value

    @property
    def is_moving(self) -> bool:
        return self._robot_moving

    @property
    def target_position(self) -> Optional[List[float]]:
        return self._target_position

    @target_position.setter
    def target_position(self, value: Optional[List[float]]):
        self._target_position = value

    @property
    def last_position_error(self) -> Optional[List[float]]:
        return self._last_position_error

    @property
    def last_rotation_error(self) -> Optional[List[float]]:
        return self._last_rotation_error

    @property
    def last_joint_error(self) -> Optional[List[float]]:
        return self._last_joint_error


    def update_joint_state(self, positions_rad: List[float]):
        if len(positions_rad) >= 6:
            self._current_joint_position = [
                pos * 180.0 / math.pi for pos in positions_rad[:6]
            ]
            self.joint_position_updated.emit(self._current_joint_position)

    def update_tcp_pose(self, x_m: float, y_m: float, z_m: float,
                        qx: float, qy: float, qz: float, qw: float):
        x = x_m * 1000.0
        y = y_m * 1000.0
        z = z_m * 1000.0

        rx, ry, rz = self._quaternion_to_euler_deg(qx, qy, qz, qw)

        self._current_tcp_pose = [x, y, z, rx, ry, rz]
        self.tcp_pose_updated.emit(self._current_tcp_pose)

    def update_feedback_state(self, tcp_speed: List[float], joint_vel: List[float]):
        tcp_speed_norm = 0.0
        if tcp_speed and len(tcp_speed) >= 3:
            tcp_speed_norm = math.sqrt(sum(v**2 for v in tcp_speed[:3]))

        joint_speed_norm = 0.0
        if joint_vel and len(joint_vel) >= 6:
            joint_speed_norm = math.sqrt(sum(v**2 for v in joint_vel))

        old_moving = self._robot_moving
        self._robot_moving = (tcp_speed_norm > 0.5) or (joint_speed_norm > 0.01)

        if old_moving != self._robot_moving:
            self.motion_state_changed.emit(self._robot_moving)


    def check_motion_complete(self) -> bool:
        if self._target_position is None:
            return False

        if self._current_tcp_pose and len(self._current_tcp_pose) >= 6:
            target_mm_deg = [
                self._target_position[0] * 1000.0,
                self._target_position[1] * 1000.0,
                self._target_position[2] * 1000.0,
                self._target_position[3] * 180.0 / math.pi,
                self._target_position[4] * 180.0 / math.pi,
                self._target_position[5] * 180.0 / math.pi
            ]

            pos_errors = [
                abs(target_mm_deg[i] - self._current_tcp_pose[i])
                for i in range(3)
            ]
            rot_errors = [
                self._angle_difference_deg(target_mm_deg[i], self._current_tcp_pose[i])
                for i in range(3, 6)
            ]

            position_ok = (
                all(pos_errors[i] < 5.0 for i in range(3)) and
                all(rot_errors[i] < 2.0 for i in range(3))
            )

            self._last_position_error = pos_errors
            self._last_rotation_error = rot_errors

        elif self._current_joint_position and len(self._current_joint_position) >= 6:
            target_deg = [
                self._target_position[i] * 180.0 / math.pi for i in range(6)
            ]
            errors = [
                self._angle_difference_deg(target_deg[i], self._current_joint_position[i])
                for i in range(6)
            ]
            position_ok = all(errors[i] < 1.0 for i in range(6))

            self._last_joint_error = errors
        else:
            return False

        velocity_ok = not self._robot_moving

        return position_ok and velocity_ok

    def get_motion_complete_message(self) -> str:
        msg = "이동 완료"
        if self._last_position_error is not None and self._last_rotation_error is not None:
            msg += f" (오차: 위치 {self._last_position_error[0]:.2f}, "
            msg += f"{self._last_position_error[1]:.2f}, {self._last_position_error[2]:.2f} mm, "
            msg += f"회전 {self._last_rotation_error[0]:.3f}, "
            msg += f"{self._last_rotation_error[1]:.3f}, {self._last_rotation_error[2]:.3f}°)"
        elif self._last_joint_error is not None:
            msg += f" (관절 오차: {', '.join([f'{e:.3f}°' for e in self._last_joint_error])})"
        return msg

    def clear_motion_state(self):
        self._target_position = None
        self._last_position_error = None
        self._last_rotation_error = None
        self._last_joint_error = None


    @staticmethod
    def _quaternion_to_euler_deg(qx: float, qy: float, qz: float, qw: float) -> Tuple[float, float, float]:
        sinr_cosp = 2 * (qw * qx + qy * qz)
        cosr_cosp = 1 - 2 * (qx * qx + qy * qy)
        rx = math.atan2(sinr_cosp, cosr_cosp) * 180.0 / math.pi

        sinp = 2 * (qw * qy - qz * qx)
        if abs(sinp) >= 1:
            ry = math.copysign(90.0, sinp)
        else:
            ry = math.asin(sinp) * 180.0 / math.pi

        siny_cosp = 2 * (qw * qz + qx * qy)
        cosy_cosp = 1 - 2 * (qy * qy + qz * qz)
        rz = math.atan2(siny_cosp, cosy_cosp) * 180.0 / math.pi

        return rx, ry, rz

    @staticmethod
    def _normalize_angle_deg(angle: float) -> float:
        while angle > 180.0:
            angle -= 360.0
        while angle < -180.0:
            angle += 360.0
        return angle

    def _angle_difference_deg(self, target: float, current: float) -> float:
        diff = target - current
        return abs(self._normalize_angle_deg(diff))
