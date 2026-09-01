"""비전 기준점(원점) 학습·판정 — positions.yaml 의 vision_origin_check 절 담당."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .config_manager import ConfigManager

POSE_KEYS = ('x', 'y', 'z', 'rx', 'ry', 'rz')
POSITION_KEYS = ('x', 'y', 'z')
ROTATION_KEYS = ('rx', 'ry', 'rz')

CONFIG_ROOT = 'vision_origin_check'

# 기본 허용 편차 — 위치 mm, 회전 deg
DEFAULT_TOLERANCE_XYZ = 1.0
DEFAULT_TOLERANCE_RPY = 0.5


@dataclass
class VisionOriginCheckResult:
    """기준점 판정 결과 (통과 여부·축별 편차·초과 축·사용 허용범위)."""
    passed: bool
    deltas: Dict[str, float]
    failed_axes: List[str]
    tolerance: Dict[str, float]
    measured: Dict[str, float]
    reference: Dict[str, float]
    message: str


def normalize_angle_deg(angle: float) -> float:
    """각도를 ±180° 범위로 정규화한다 (deg)."""
    return (float(angle) + 180.0) % 360.0 - 180.0


class VisionOriginCheckService:
    """학습 기준(TCP 자세+랜드마크)과 측정 pose 의 6축 편차를 판정한다.

    기준·허용범위는 ConfigManager 로 positions.yaml 에 저장한다 — 미주입 시
    자체 인스턴스를 만들며, 이 경우 앱의 다른 ConfigManager 캐시와 어긋날 수
    있으므로 루트에서 단일 인스턴스 주입이 안전하다.
    """

    def __init__(self, config_manager: Optional[ConfigManager] = None,
                 log_callback: Optional[Callable[[str], None]] = None):
        self.config_manager = config_manager or ConfigManager()
        self._log_callback = log_callback

    def _log(self, message: str) -> None:
        if self._log_callback:
            self._log_callback(message)

    @staticmethod
    def is_pose(value: Any) -> bool:
        """6축 키가 모두 수치인 pose dict 인지 검사한다."""
        if not isinstance(value, dict):
            return False
        return all(isinstance(value.get(key), (int, float)) for key in POSE_KEYS)

    @staticmethod
    def _clean_pose(pose: Dict[str, Any]) -> Dict[str, float]:
        return {key: float(pose[key]) for key in POSE_KEYS}

    @staticmethod
    def _positive_float(value: Any, fallback: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return fallback
        return number if number > 0 else fallback

    def has_reference(self) -> bool:
        """학습된 기준이 유효 구조로 존재하는지."""
        return self.load_reference() is not None

    def load_reference(self) -> Optional[Dict[str, Any]]:
        """저장 기준을 구조 검증(landmark·tcp_pose 필수) 후 돌려준다."""
        data = self.config_manager.get(CONFIG_ROOT)
        if not isinstance(data, dict):
            return None
        if not self.is_pose(data.get('landmark')) or not self.is_pose(data.get('tcp_pose')):
            return None
        return data

    def get_reference_tcp_pose(self) -> Optional[List[float]]:
        """학습 시점 TCP 자세 [x,y,z,rx,ry,rz] (mm/deg) — 측정 전 복귀 목표."""
        reference = self.load_reference()
        if reference is None:
            return None
        tcp_pose = reference['tcp_pose']
        return [float(tcp_pose[key]) for key in POSE_KEYS]

    def save_reference(self, tcp_pose: Dict[str, float], landmark: Dict[str, float],
                       measure: Optional[Dict[str, Any]] = None,
                       std: Optional[Dict[str, float]] = None) -> bool:
        """기준(TCP 자세+랜드마크+허용범위+측정 조건)을 저장한다."""
        if not self.is_pose(tcp_pose):
            self._log("기준점 저장 실패: TCP 자세에 x,y,z,rx,ry,rz 가 모두 필요합니다")
            return False
        if not self.is_pose(landmark):
            self._log("기준점 저장 실패: Landmark 좌표에 x,y,z,rx,ry,rz 가 모두 필요합니다")
            return False

        record: Dict[str, Any] = {
            'learned_at': datetime.now().isoformat(timespec='seconds'),
            'tcp_pose': self._clean_pose(tcp_pose),
            'landmark': self._clean_pose(landmark),
            'tolerance': self.get_tolerance(),
        }

        if isinstance(measure, dict):
            record['measure'] = {
                'repeat_count': int(measure.get('repeat_count', 1)),
                'outlier_method': str(measure.get('outlier_method', 'none')),
            }
        if self.is_pose(std):
            record['learned_std'] = self._clean_pose(std)

        try:
            self.config_manager.set(CONFIG_ROOT, record)
        except Exception as e:
            self._log(f"기준점 저장 실패: {e}")
            return False

        self._log(f"기준점 학습 완료: X={record['landmark']['x']:.3f}, "
                  f"Y={record['landmark']['y']:.3f}, Z={record['landmark']['z']:.3f}")
        return True

    def get_tolerance(self) -> Dict[str, float]:
        """허용범위 {'xyz': mm, 'rpy': deg} — 저장값이 없거나 비양수면 기본값."""
        stored = self.config_manager.get(f'{CONFIG_ROOT}.tolerance')
        xyz = DEFAULT_TOLERANCE_XYZ
        rpy = DEFAULT_TOLERANCE_RPY
        if isinstance(stored, dict):
            xyz = self._positive_float(stored.get('xyz'), xyz)
            rpy = self._positive_float(stored.get('rpy'), rpy)
        return {'xyz': xyz, 'rpy': rpy}

    def set_tolerance(self, xyz: float, rpy: float) -> bool:
        """허용범위(xyz mm / rpy deg)를 양수 검증 후 저장한다."""
        try:
            xyz_value = float(xyz)
            rpy_value = float(rpy)
        except (TypeError, ValueError):
            self._log("허용범위 저장 실패: 숫자가 아닙니다")
            return False

        if xyz_value <= 0 or rpy_value <= 0:
            self._log("허용범위 저장 실패: 0 보다 큰 값이어야 합니다")
            return False

        try:
            self.config_manager.set(f'{CONFIG_ROOT}.tolerance',
                                    {'xyz': xyz_value, 'rpy': rpy_value})
        except Exception as e:
            self._log(f"허용범위 저장 실패: {e}")
            return False

        self._log(f"허용범위 저장 완료: XYZ={xyz_value:.3f}mm, RxRyRz={rpy_value:.3f}deg")
        return True

    def evaluate(self, measured: Dict[str, float],
                 tolerance: Optional[Dict[str, float]] = None) -> Optional[VisionOriginCheckResult]:
        """측정 pose 와 기준 랜드마크의 6축 편차를 판정한다.

        측정과 기준은 같은 좌표계(RobotBase)라는 전제. 회전 편차는 ±180°
        정규화 후 비교. 기준 부재·측정 구조 오류면 None.
        """
        reference = self.load_reference()
        if reference is None:
            self._log("기준점이 학습되지 않았습니다")
            return None

        if not self.is_pose(measured):
            self._log("기준점 판정 실패: 측정값에 x,y,z,rx,ry,rz 가 모두 필요합니다")
            return None

        reference_landmark = self._clean_pose(reference['landmark'])
        tolerance = tolerance if isinstance(tolerance, dict) else self.get_tolerance()
        limit_xyz = self._positive_float(tolerance.get('xyz'), DEFAULT_TOLERANCE_XYZ)
        limit_rpy = self._positive_float(tolerance.get('rpy'), DEFAULT_TOLERANCE_RPY)

        deltas: Dict[str, float] = {}
        failed_axes: List[str] = []

        for key in POSITION_KEYS:
            delta = float(measured[key]) - reference_landmark[key]
            deltas[key] = delta
            if abs(delta) > limit_xyz:
                failed_axes.append(key)

        for key in ROTATION_KEYS:
            delta = normalize_angle_deg(float(measured[key]) - reference_landmark[key])
            deltas[key] = delta
            if abs(delta) > limit_rpy:
                failed_axes.append(key)

        passed = not failed_axes
        if passed:
            message = f"기준점 확인 통과 ({self.format_deltas(deltas)})"
        else:
            message = (f"기준점 확인 실패 — 허용범위 초과 축: {', '.join(failed_axes)} "
                       f"({self.format_deltas(deltas)}) / "
                       f"허용범위 XYZ={limit_xyz:.3f}mm, RxRyRz={limit_rpy:.3f}deg")

        return VisionOriginCheckResult(
            passed=passed,
            deltas=deltas,
            failed_axes=failed_axes,
            tolerance={'xyz': limit_xyz, 'rpy': limit_rpy},
            measured=self._clean_pose(measured),
            reference=reference_landmark,
            message=message,
        )

    @staticmethod
    def format_deltas(deltas: Dict[str, float]) -> str:
        """축별 편차를 'dX=... mm / dRx=... deg' 문자열로 만든다."""
        position = ' '.join(f"d{key.upper()}={deltas[key]:+.3f}" for key in POSITION_KEYS)
        rotation = ' '.join(f"d{key.capitalize()}={deltas[key]:+.3f}" for key in ROTATION_KEYS)
        return f"{position} mm / {rotation} deg"
