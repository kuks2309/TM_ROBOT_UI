"""로봇 상태 캐시·이동 완료 판정 — 구독 콜백이 넣고 GUI 가 읽는다 (mm/deg 캐시)."""
import math
from typing import Optional, List, Tuple
from PyQt5.QtCore import QObject, pyqtSignal


TM_JOINT_NAMES = ('joint_1', 'joint_2', 'joint_3', 'joint_4', 'joint_5', 'joint_6')


def is_tm_joint_state(names, positions) -> bool:
    """JointState 가 TM 6축 것인지 판별한다 (이름 없으면 개수 6으로 추정)."""
    if positions is None or len(positions) < 6:
        return False
    if names:
        return tuple(names[:6]) == TM_JOINT_NAMES
    return len(positions) == 6


class RobotMotionService(QObject):
    """조인트(deg)·TCP(mm/deg) 캐시와 목표 대비 완료 판정.

    update_* 는 루트 노드 구독 콜백(executor 스레드)에서, property 읽기·판정은
    GUI 스레드에서 온다 — 캐시는 리스트 재대입이라 찢김 없음.
    target_position 은 SetPositions 요청 그대로의 서비스 단위(m/rad)로 저장한다.
    """

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
        """(노드 콜백) 조인트 rad 를 deg 로 캐시하고 시그널 발행."""
        if len(positions_rad) >= 6:
            self._current_joint_position = [
                pos * 180.0 / math.pi for pos in positions_rad[:6]
            ]
            self.joint_position_updated.emit(self._current_joint_position)

    def update_tcp_pose(self, x_m: float, y_m: float, z_m: float,
                        qx: float, qy: float, qz: float, qw: float):
        """(노드 콜백) PoseStamped 성분을 mm/deg 로 변환해 캐시하고 시그널 발행."""
        x = x_m * 1000.0
        y = y_m * 1000.0
        z = z_m * 1000.0

        rx, ry, rz = self._quaternion_to_euler_deg(qx, qy, qz, qw)

        self._current_tcp_pose = [x, y, z, rx, ry, rz]
        self.tcp_pose_updated.emit(self._current_tcp_pose)

    def update_feedback_state(self, tcp_speed: List[float], joint_vel: List[float]):
        """(노드 콜백) FeedbackState 속도 놈으로 이동 중 여부를 판정한다.

        문턱: tcp 놈 > 0.5 또는 joint 놈 > 0.01 — 단위는 벤더 FeedbackState
        필드 규약에 종속(코드에서 미확정). 판정 변화 시에만 시그널 발행.
        """
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
        """목표 대비 오차와 정지 여부로 이동 완료를 판정한다.

        허용오차: TCP 위치 5mm·회전 2°, 조인트 1° — 여기에 로봇이 정지 상태
        (is_moving False)여야 완료다. 판정에 쓴 오차는 last_*_error 에 남긴다.
        """
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
        """직전 판정의 오차를 담은 완료 문구를 만든다."""
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
        """목표·오차 기록을 지워 완료 판정을 비활성화한다."""
        self._target_position = None
        self._last_position_error = None
        self._last_rotation_error = None
        self._last_joint_error = None


    @staticmethod
    def _quaternion_to_euler_deg(qx: float, qy: float, qz: float, qw: float) -> Tuple[float, float, float]:
        """쿼터니언을 오일러(deg)로 — 짐벌락은 ry=±90° 고정."""
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
