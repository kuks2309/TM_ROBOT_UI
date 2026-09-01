"""정적 좌표/단위 변환 유틸 — GUI 단위(mm/deg/%)와 SetPositions 단위(m/rad) 사이."""
import math
from typing import List, Tuple

# 속도 100% 에 대응하는 서비스 값 상한
MAX_JOINT_VELOCITY = math.pi   # rad/s (조인트·PTP 계열)
MAX_TCP_SPEED = 1.0            # m/s (LINE_T)

# tm_msgs SetPositions.Request.LINE_T 와 같은 값의 로컬 재정의 —
# 벤더 상수가 바뀌면 함께 어긋나므로 주의
_MOTION_LINE_T = 4


class CoordinateTransformer:
    """전부 staticmethod 인 순수 변환 함수 모음."""

    @staticmethod
    def velocity_percent_to_service(motion_type: int, percent: float) -> float:
        """속도 % 를 서비스 값으로 — LINE_T 는 m/s, 그 외는 rad/s (0~100 클램프)."""
        ratio = max(0.0, min(percent, 100.0)) / 100.0
        if motion_type == _MOTION_LINE_T:
            return ratio * MAX_TCP_SPEED
        return ratio * MAX_JOINT_VELOCITY

    @staticmethod
    def euler_to_rotation_matrix(rx: float, ry: float, rz: float) -> List[List[float]]:
        """오일러 각(rad)에서 Rz·Ry·Rx 합성 3x3 회전행렬 — 입력이 rad 임에 주의."""
        cos_rx, sin_rx = math.cos(rx), math.sin(rx)
        cos_ry, sin_ry = math.cos(ry), math.sin(ry)
        cos_rz, sin_rz = math.cos(rz), math.sin(rz)

        R = [
            [cos_rz*cos_ry, cos_rz*sin_ry*sin_rx - sin_rz*cos_rx, cos_rz*sin_ry*cos_rx + sin_rz*sin_rx],
            [sin_rz*cos_ry, sin_rz*sin_ry*sin_rx + cos_rz*cos_rx, sin_rz*sin_ry*cos_rx - cos_rz*sin_rx],
            [-sin_ry,       cos_ry*sin_rx,                        cos_ry*cos_rx]
        ]
        return R

    @staticmethod
    def quaternion_to_euler(qx: float, qy: float, qz: float, qw: float) -> Tuple[float, float, float]:
        """쿼터니언을 오일러 각(deg)으로 — 짐벌락은 ry=±90° 로 고정."""
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
    def transform_tool_to_base(tool_delta: List[float],
                              tcp_orientation: List[float]) -> List[float]:
        """공구 좌표계 변위(mm)를 TCP 자세(deg)로 회전시켜 베이스 변위로 바꾼다."""
        rx = tcp_orientation[0] * math.pi / 180.0
        ry = tcp_orientation[1] * math.pi / 180.0
        rz = tcp_orientation[2] * math.pi / 180.0

        R = CoordinateTransformer.euler_to_rotation_matrix(rx, ry, rz)

        base_delta = [
            R[0][0]*tool_delta[0] + R[0][1]*tool_delta[1] + R[0][2]*tool_delta[2],
            R[1][0]*tool_delta[0] + R[1][1]*tool_delta[1] + R[1][2]*tool_delta[2],
            R[2][0]*tool_delta[0] + R[2][1]*tool_delta[1] + R[2][2]*tool_delta[2]
        ]

        return base_delta

    @staticmethod
    def angle_difference_deg(target: float, current: float) -> float:
        """±180° 랩어라운드를 고려한 최단 각도차 절댓값(deg)."""
        diff = (target - current + 180.0) % 360.0 - 180.0
        return abs(diff)

    @staticmethod
    def deg_to_rad(angle_deg: float) -> float:
        return angle_deg * math.pi / 180.0

    @staticmethod
    def rad_to_deg(angle_rad: float) -> float:
        return angle_rad * 180.0 / math.pi

    @staticmethod
    def mm_to_m(value_mm: float) -> float:
        return value_mm / 1000.0

    @staticmethod
    def m_to_mm(value_m: float) -> float:
        return value_m * 1000.0

    @staticmethod
    def convert_tcp_to_service_format(tcp_pose: List[float]) -> List[float]:
        """TCP pose(mm/deg)를 SetPositions 형식(m/rad)으로 변환한다."""
        return [
            CoordinateTransformer.mm_to_m(tcp_pose[0]),
            CoordinateTransformer.mm_to_m(tcp_pose[1]),
            CoordinateTransformer.mm_to_m(tcp_pose[2]),
            CoordinateTransformer.deg_to_rad(tcp_pose[3]),
            CoordinateTransformer.deg_to_rad(tcp_pose[4]),
            CoordinateTransformer.deg_to_rad(tcp_pose[5])
        ]

    @staticmethod
    def convert_joint_to_service_format(joint_pose: List[float]) -> List[float]:
        """조인트 각(deg)을 SetPositions 형식(rad)으로 변환한다."""
        return [CoordinateTransformer.deg_to_rad(j) for j in joint_pose]
