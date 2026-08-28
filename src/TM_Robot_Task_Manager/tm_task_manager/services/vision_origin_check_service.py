"""로봇 기준점 확인 — 학습값 영속화와 6축 개별 편차 판정.

측정 원리상 `g_TM_Landmark` 는 `T_base_tcp × T_tcp_cam × T_cam_mark` 로 합성되어
로봇 기구학 오차를 포함한다. 그래서 기준값은 landmark 단독이 아니라
`(tcp_pose, landmark)` 쌍으로 저장하며, 확인 시 같은 TCP 자세로 복귀해 측정해야
편차가 자세 차이에 오염되지 않는다. 설계 근거: docs/adr/2026-08-10-reference-point-check.md
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .config_manager import ConfigManager

POSE_KEYS = ('x', 'y', 'z', 'rx', 'ry', 'rz')
POSITION_KEYS = ('x', 'y', 'z')
ROTATION_KEYS = ('rx', 'ry', 'rz')

CONFIG_ROOT = 'vision_origin_check'

# 잠정 기본값 — jig_plate_validator 의 기존 임계값(TOLERANCE_Z_DEVIATION 1.0mm,
# TOLERANCE_ANGLE 0.5deg)에서 가져왔다. 현장에서 learned_std 를 보고 조정해야 한다.
DEFAULT_TOLERANCE_XYZ = 1.0
DEFAULT_TOLERANCE_RPY = 0.5


@dataclass
class VisionOriginCheckResult:
    """기준점 확인 판정 결과.

    deltas: 축별 (측정 - 기준). x/y/z 는 mm, rx/ry/rz 는 deg(±180 정규화).
    failed_axes: 허용범위를 초과한 축 이름 목록. 비어 있으면 통과.
    """
    passed: bool
    deltas: Dict[str, float]
    failed_axes: List[str]
    tolerance: Dict[str, float]
    measured: Dict[str, float]
    reference: Dict[str, float]
    message: str


def normalize_angle_deg(angle: float) -> float:
    """회전 편차를 [-180, 180) 으로 접는다.

    179deg 와 -179deg 의 실제 차이는 2deg 지만 단순 뺄셈은 358deg 를 준다.
    이 정규화가 없으면 ±180 경계에 놓인 마크에서 정상 상태가 알람으로 잡힌다.
    """
    return (float(angle) + 180.0) % 360.0 - 180.0


class VisionOriginCheckService:
    """기준점 학습값·허용범위 영속화와 편차 판정. UI 를 직접 조작하지 않는다."""

    def __init__(self, config_manager: Optional[ConfigManager] = None,
                 log_callback: Optional[Callable[[str], None]] = None):
        self.config_manager = config_manager or ConfigManager()
        self._log_callback = log_callback

    def _log(self, message: str) -> None:
        if self._log_callback:
            self._log_callback(message)

    @staticmethod
    def is_pose(value: Any) -> bool:
        """6축 키(x,y,z,rx,ry,rz)를 모두 갖춘 dict 인지."""
        if not isinstance(value, dict):
            return False
        return all(isinstance(value.get(key), (int, float)) for key in POSE_KEYS)

    @staticmethod
    def _clean_pose(pose: Dict[str, Any]) -> Dict[str, float]:
        """YAML 에 저장 가능한 순수 float dict 로 정규화(numpy 스칼라 차단)."""
        return {key: float(pose[key]) for key in POSE_KEYS}

    @staticmethod
    def _positive_float(value: Any, fallback: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return fallback
        return number if number > 0 else fallback

    def has_reference(self) -> bool:
        """학습된 기준점이 있는지."""
        return self.load_reference() is not None

    def load_reference(self) -> Optional[Dict[str, Any]]:
        """학습값 전체를 반환. 미학습이거나 형식이 깨졌으면 None."""
        data = self.config_manager.get(CONFIG_ROOT)
        if not isinstance(data, dict):
            return None
        if not self.is_pose(data.get('landmark')) or not self.is_pose(data.get('tcp_pose')):
            return None
        return data

    def get_reference_tcp_pose(self) -> Optional[List[float]]:
        """학습 시 TCP 자세를 [x, y, z, rx, ry, rz] (mm, deg) 로 반환. 미학습이면 None."""
        reference = self.load_reference()
        if reference is None:
            return None
        tcp_pose = reference['tcp_pose']
        return [float(tcp_pose[key]) for key in POSE_KEYS]

    def save_reference(self, tcp_pose: Dict[str, float], landmark: Dict[str, float],
                       measure: Optional[Dict[str, Any]] = None,
                       std: Optional[Dict[str, float]] = None) -> bool:
        """기준점을 학습·저장한다.

        tcp_pose: 학습 시 로봇 TCP 자세 (RobotBase 기준, mm/deg)
        landmark: 그 자세에서 측정된 TM Landmark 좌표 (RobotBase 기준, mm/deg)
        measure:  학습에 쓴 측정 조건 {'repeat_count': int, 'outlier_method': str}
        std:      학습 시 축별 표준편차 — 허용범위 타당성 참고값
        반환: 저장 성공 여부. 기존 허용범위는 보존된다.
        """
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
        """허용범위를 {'xyz': mm, 'rpy': deg} 로 반환. 미설정·비정상값은 기본값으로 대체."""
        stored = self.config_manager.get(f'{CONFIG_ROOT}.tolerance')
        xyz = DEFAULT_TOLERANCE_XYZ
        rpy = DEFAULT_TOLERANCE_RPY
        if isinstance(stored, dict):
            xyz = self._positive_float(stored.get('xyz'), xyz)
            rpy = self._positive_float(stored.get('rpy'), rpy)
        return {'xyz': xyz, 'rpy': rpy}

    def set_tolerance(self, xyz: float, rpy: float) -> bool:
        """허용범위를 저장한다. xyz(mm)·rpy(deg) 는 0 보다 커야 한다.

        0 이하를 허용하면 어떤 측정도 통과할 수 없어 알람이 상시 발생한다.
        """
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
        """측정값을 기준값과 6축 개별 비교한다.

        measured: 측정된 Landmark 좌표 (RobotBase 기준, mm/deg)
        tolerance: 생략 시 저장된 허용범위 사용
        반환: 판정 결과. 미학습이거나 측정값 형식이 잘못되면 None.
        판정: |편차| 가 허용범위와 같으면 통과, 초과해야 실패.
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
        """축별 편차를 로그·UI 공용 한 줄 문자열로. 단위는 mm / deg."""
        position = ' '.join(f"d{key.upper()}={deltas[key]:+.3f}" for key in POSITION_KEYS)
        rotation = ' '.join(f"d{key.capitalize()}={deltas[key]:+.3f}" for key in ROTATION_KEYS)
        return f"{position} mm / {rotation} deg"
