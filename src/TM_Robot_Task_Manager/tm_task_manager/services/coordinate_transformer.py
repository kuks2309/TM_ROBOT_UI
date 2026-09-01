"""정적 좌표/단위 변환 유틸 — GUI 단위(mm/deg/%)와 SetPositions 단위(m/rad) 사이."""
import math
from typing import List, Tuple

# 속도 100% 에 대응하는 서비스 값 상한
MAX_JOINT_VELOCITY = math.pi   # rad/s (조인트·PTP 계열)
MAX_TCP_SPEED = 1.0            # m/s (LINE_T)

# tm_msgs SetPositions.Request.LINE_T 와 같은 값의 로컬 재정의 —
# 벤더 상수가 바뀌면 함께 어긋나므로 주의
_MOTION_LINE_T = 4

# 이동 완료 대기 한도(s) — 거리·속도로 예상 소요시간을 구해 동적으로 정한다.
# 저속·장거리 이동이 고정 한도에 걸려 실패하던 문제를 막되, 상한으로 무한 대기는 차단.
MOTION_TIMEOUT_MIN_S = 30.0    # 짧은 이동도 최소 이만큼은 기다린다 (종전 고정값과 동일)
MOTION_TIMEOUT_MAX_S = 300.0   # 예상치가 커도 이 이상은 기다리지 않는다
MOTION_TIMEOUT_BASE_S = 10.0   # 통신 지연·가감속·정지 판정 3회 등 거리와 무관한 고정 여유
MOTION_TIMEOUT_MARGIN = 3.0    # 예상 소요시간 배수 — 로봇 내부 속도 제한·블렌딩·PTP 경로 우회 여유
_MIN_VELOCITY_RATIO = 0.01     # 속도 0% 입력 시 0 나눗셈 방지 (1% 로 간주)


def estimate_motion_timeout_s(kind: str, target_service: List[float], velocity_percent: float,
                              current_tcp_mm_deg=None, current_joint_deg=None) -> float:
    """이동 명령의 완료 대기 한도(s)를 목표까지 거리와 속도(%)로 추정한다.

    Args:
        kind: 'joint'(PTP_J) / 'tcp'(PTP_T) / 'line'(LINE_T).
        target_service: SetPositions 서비스 단위 목표 — joint 는 rad 6개, tcp/line 은 m·rad 6개.
        velocity_percent: 속도 % (0~100, 100% = MAX_JOINT_VELOCITY 또는 MAX_TCP_SPEED).
        current_tcp_mm_deg: 현재 TCP [x,y,z(mm), rx,ry,rz(deg)] — 없으면 거리 추정 불가.
        current_joint_deg: 현재 관절각 deg 6개 — joint 이동의 거리 추정에 사용.

    Returns:
        BASE + MARGIN×예상시간 을 [MIN, MAX] 로 클램프한 값. 현재 위치를 몰라 거리를 못 구하면 MIN.
    """
    ratio = max(_MIN_VELOCITY_RATIO, min(float(velocity_percent), 100.0) / 100.0)
    est_s = None

    if kind == 'joint':
        if current_joint_deg and len(current_joint_deg) >= 6 and len(target_service) >= 6:
            max_delta_rad = max(
                abs(math.radians(float(current_joint_deg[i])) - float(target_service[i]))
                for i in range(6))
            est_s = max_delta_rad / (ratio * MAX_JOINT_VELOCITY)
    else:
        if current_tcp_mm_deg and len(current_tcp_mm_deg) >= 6 and len(target_service) >= 6:
            dist_m = math.sqrt(sum(
                (float(current_tcp_mm_deg[i]) / 1000.0 - float(target_service[i])) ** 2
                for i in range(3)))
            # 자세 변화는 관절 속도에 묶이므로 회전량(rad)/관절 상한으로 별도 추정해 큰 쪽을 쓴다
            max_rot_rad = max(
                abs(math.radians(float(current_tcp_mm_deg[i])) - float(target_service[i]))
                for i in range(3, 6))
            trans_s = dist_m / (ratio * MAX_TCP_SPEED)
            rot_s = max_rot_rad / (ratio * MAX_JOINT_VELOCITY)
            est_s = max(trans_s, rot_s)

    if est_s is None:
        return MOTION_TIMEOUT_MIN_S
    timeout = MOTION_TIMEOUT_BASE_S + MOTION_TIMEOUT_MARGIN * est_s
    return max(MOTION_TIMEOUT_MIN_S, min(timeout, MOTION_TIMEOUT_MAX_S))


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
