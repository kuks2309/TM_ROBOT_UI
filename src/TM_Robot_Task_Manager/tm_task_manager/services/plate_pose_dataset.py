"""plate_pose_calc 측정 데이터셋 로더/통계 — jig 시계열·편차·기하 리포트 (mm/deg)."""
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

# jig_plate_validator 상단이 PyQt5·matplotlib 를 무조건 import 하므로
# 이 모듈을 쓰는 헤드리스 사용처에도 GUI 의존성이 연쇄 로드된다
from ..tools.jig_plate_validator import JigPlateValidator

JIG_KEYS: Tuple[str, ...] = ('jig1', 'jig2', 'jig3', 'jig4')
POSE_AXES: Tuple[str, ...] = ('x', 'y', 'z', 'rx', 'ry', 'rz')
ANGLE_AXES: Tuple[str, ...] = ('rx', 'ry', 'rz')
DATASET_DIR_NAME = 'plate_pose_calc'
CORRECTED_SUBDIR = 'corrected'

VARIANT_RAW = 'raw'
VARIANT_CORRECTED = 'corrected'


@dataclass
class PlateRecord:
    """측정 파일 1건 — 평면 pose 와 표준 순서로 정렬된 jig 4점."""
    file_name: str
    saved_at: str
    plate_pose: Dict[str, float]
    jigs: List[Dict[str, float]]


@dataclass
class AxisStat:
    """한 jig·한 축의 통계 (평균·std·3σ·최소/최대 — 위치 mm, 각도 deg)."""
    target: str
    axis: str
    count: int
    mean: float
    std: float
    sigma3: float
    minimum: float
    maximum: float

    @property
    def value_range(self) -> float:
        return self.maximum - self.minimum


def normalize_jig_order(marks: List[Dict[str, float]]) -> List[Dict[str, float]]:
    """마크 4점을 장변/단변 기준의 표준 jig 순서로 정렬한다.

    파일마다 저장 순서가 달라도 같은 물리 지그가 같은 인덱스로 비교되게 한다
    — JigPlaneCalculator 의 순서 계약(1=좌하, 2=좌상, 3=우하, 4=우상)에 대응.
    """
    if len(marks) != 4:
        return list(marks)

    span_x = max(m['x'] for m in marks) - min(m['x'] for m in marks)
    span_y = max(m['y'] for m in marks) - min(m['y'] for m in marks)

    long_axis, short_axis = ('x', 'y') if span_x >= span_y else ('y', 'x')

    by_short = sorted(marks, key=lambda m: m[short_axis])
    low_group = sorted(by_short[:2], key=lambda m: m[long_axis], reverse=True)
    high_group = sorted(by_short[2:], key=lambda m: m[long_axis], reverse=True)

    return [high_group[0], low_group[0], high_group[1], low_group[1]]


class PlatePoseDataset:
    """data/plate_pose_calc/<팔레트>/ 의 raw/corrected 측정 yaml 묶음을 다룬다."""

    def __init__(self):
        self.root: Optional[Path] = None
        self.records: List[PlateRecord] = []
        self.pallet: Optional[str] = None
        self.variant: str = VARIANT_CORRECTED

    @staticmethod
    def default_root() -> Path:
        from .. import paths
        return paths.DATA_DIR / DATASET_DIR_NAME

    def set_root(self, root_path) -> bool:
        """루트를 설정한다 — 디렉토리이고 팔레트 하위 폴더가 있어야 True."""
        root = Path(root_path)
        if not root.is_dir():
            return False
        self.root = root
        return bool(self.list_pallets())

    def list_pallets(self) -> List[str]:
        if self.root is None or not self.root.is_dir():
            return []
        return sorted(d.name for d in self.root.iterdir() if d.is_dir())

    def _variant_files(self, pallet: str, variant: str) -> List[Path]:
        if self.root is None:
            return []
        pallet_dir = self.root / pallet
        if variant == VARIANT_CORRECTED:
            return sorted((pallet_dir / CORRECTED_SUBDIR).glob('*.yaml'))
        return sorted(p for p in pallet_dir.glob('*.yaml') if p.is_file())

    def load(self, pallet: str, variant: str = VARIANT_CORRECTED) -> Tuple[bool, str]:
        """팔레트의 measurement yaml 전체를 파싱해 records 로 적재한다.

        Returns:
            (성공 여부, 요약 문구 — 건너뛴 파일 수 포함).
        """
        files = self._variant_files(pallet, variant)
        if not files:
            return False, f"{pallet}/{variant}: YAML 파일이 없습니다."

        records: List[PlateRecord] = []
        skipped: List[str] = []

        for path in files:
            record = self._parse_file(path)
            if record is None:
                skipped.append(path.name)
                continue
            records.append(record)

        if not records:
            return False, f"{pallet}/{variant}: 읽을 수 있는 파일이 없습니다 ({len(skipped)}개 건너뜀)."

        self.records = records
        self.pallet = pallet
        self.variant = variant

        message = f"{pallet}/{variant}: {len(records)}개 로드"
        if skipped:
            message += f" ({len(skipped)}개 건너뜀: {', '.join(skipped[:3])}…)"
        return True, message

    def _parse_file(self, path: Path) -> Optional[PlateRecord]:
        """yaml 1건을 레코드로 파싱한다 — jig1~4 가 모두 없으면 None."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except (OSError, yaml.YAMLError):
            return None

        if not isinstance(data, dict):
            return None

        landmarks = data.get('landmarks')
        if not isinstance(landmarks, dict):
            return None

        marks: List[Dict[str, float]] = []
        for key in JIG_KEYS:
            entry = landmarks.get(key)
            if not isinstance(entry, dict):
                return None
            marks.append({axis: float(entry.get(axis, 0.0)) for axis in POSE_AXES})

        plate_pose_raw = data.get('plate_pose') or {}
        plate_pose = {axis: float(plate_pose_raw.get(axis, 0.0)) for axis in POSE_AXES}

        return PlateRecord(
            file_name=path.name,
            saved_at=str(data.get('saved_at', '')),
            plate_pose=plate_pose,
            jigs=normalize_jig_order(marks),
        )

    def jig_series(self, jig_index: int) -> Dict[str, List[float]]:
        """jig 하나의 축별 시계열 (records 순서)."""
        if not 0 <= jig_index < len(JIG_KEYS):
            return {axis: [] for axis in POSE_AXES}
        return {
            axis: [r.jigs[jig_index][axis] for r in self.records]
            for axis in POSE_AXES
        }

    def jig_deviation_series(self, jig_index: int) -> Dict[str, List[float]]:
        """중심 대비 편차 시계열 — 각도 축은 원형 평균 기준 ±180° 정규화."""
        from .landmark_analyzer import angle_deviation_deg, circular_mean_deg

        series = self.jig_series(jig_index)
        if not series['x']:
            return {axis: [] for axis in POSE_AXES}

        deviations = {}
        for axis in POSE_AXES:
            values = series[axis]
            if axis in ANGLE_AXES:
                deviations[axis] = list(
                    angle_deviation_deg(values, circular_mean_deg(values)))
            else:
                center = sum(values) / len(values)
                deviations[axis] = [v - center for v in values]
        return deviations

    def jig_statistics(self, jig_index: int) -> List[AxisStat]:
        """jig 하나의 축별 AxisStat — 위치는 산술, 각도는 원형 통계로 대체한다."""
        from .landmark_analyzer import circular_mean_deg, circular_std_deg
        from .precision_test_manager import PrecisionTestManager

        series = self.jig_series(jig_index)
        if not series['x']:
            return []

        manager = PrecisionTestManager()
        for i in range(len(series['x'])):
            manager.add_measurement(*(series[axis][i] for axis in POSE_AXES))

        stats = manager.get_statistics()
        deviations = self.jig_deviation_series(jig_index)
        target = JIG_KEYS[jig_index]

        rows = []
        for axis in POSE_AXES:
            if axis in ANGLE_AXES:
                mean = circular_mean_deg(series[axis])
                std = circular_std_deg(series[axis])
            else:
                mean = getattr(stats, f'mean_{axis}')
                std = getattr(stats, f'std_{axis}')

            rows.append(AxisStat(
                target=target,
                axis=axis,
                count=len(series[axis]),
                mean=mean,
                std=std,
                sigma3=3 * std,
                minimum=mean + min(deviations[axis]),
                maximum=mean + max(deviations[axis]),
            ))
        return rows

    def all_statistics(self) -> List[AxisStat]:
        rows: List[AxisStat] = []
        for jig_index in range(len(JIG_KEYS)):
            rows.extend(self.jig_statistics(jig_index))
        return rows

    def mean_marks(self) -> List[Dict[str, float]]:
        """jig 별 산술 평균 마크 4개 (기하 검증 입력용)."""
        if not self.records:
            return []
        count = len(self.records)
        return [
            {
                axis: sum(r.jigs[i][axis] for r in self.records) / count
                for axis in POSE_AXES
            }
            for i in range(len(JIG_KEYS))
        ]

    def build_validator(self, marks: Optional[List[Dict[str, float]]] = None) -> Optional[JigPlateValidator]:
        """평균(또는 지정) 마크로 기하 검증기를 구성한다 (4점 아니면 None)."""
        target_marks = marks if marks is not None else self.mean_marks()
        if len(target_marks) != 4:
            return None

        validator = JigPlateValidator()
        if not validator.load_from_dicts(target_marks):
            return None
        return validator

    def geometry_report(self, marks: Optional[List[Dict[str, float]]] = None):
        """직사각·Z 편차 검사 결과 — (변 길이 dict, ValidationResult 목록)."""
        validator = self.build_validator(marks)
        if validator is None:
            return {}, []

        results = validator.check_rectangle() + validator.check_z_consistency()
        return validator.get_side_lengths(), results
