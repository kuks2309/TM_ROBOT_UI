"""plate_pose_calc 저장 데이터셋 로더 — 팔레트별 jig 재현성·형상 검증용.

`data/plate_pose_calc/<pallet>/*.yaml`(raw) 와 `.../corrected/*.corrected.yaml` 을 읽어
jig 순서를 검사 관례로 정규화한 뒤, 통계는 `PrecisionTestManager`, 직사각형·Z 검사는
`JigPlateValidator` 에 위임한다. 계산 로직을 새로 만들지 않고 기존 자산에 데이터를 먹인다.

주의: `JigPlateValidator.load_from_yaml()` 은 `coordinate_definitions.jig_plate` 스키마용이라
이 데이터셋과 호환되지 않는다. 반드시 `load_from_dicts()` 경로를 쓴다.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

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
    """YAML 한 개 = 한 회 측정. jigs 는 정규화된 순서(index 0..3 = jig1..jig4)."""
    file_name: str
    saved_at: str
    plate_pose: Dict[str, float]
    jigs: List[Dict[str, float]]


@dataclass
class AxisStat:
    """한 대상(jig) 의 한 축에 대한 요약 통계. 단위는 축에 따라 mm 또는 deg."""
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
    """jig 4개를 검사 관례 순서로 재배열한다.

    `JigPlateValidator` 는 index (0,2)/(1,3) 를 대향변, (0,3)/(1,2) 를 대각선으로 본다.
    raw 파일은 측정 순서대로 저장되어 이 관례와 어긋나므로(변과 대각선이 뒤바뀜) 정규화가 필요하다.
    corrected 파일은 이미 같은 규칙으로 재배열되어 있어 이 함수는 무연산(no-op)이 된다.

    규칙: 긴 변이 놓인 축을 장축으로 잡고, 단축 기준 상단/하단으로 나눈 뒤
    각 그룹에서 장축 좌표가 큰 쪽을 앞 번호로 둔다 → (0,2) 가 장변, (0,1) 이 단변이 된다.

    Args:
        marks: x/y 를 가진 dict 4개.
    Returns:
        재배열된 dict 4개. 입력이 4개가 아니면 원본을 그대로 돌려준다.
    """
    if len(marks) != 4:
        return list(marks)

    span_x = max(m['x'] for m in marks) - min(m['x'] for m in marks)
    span_y = max(m['y'] for m in marks) - min(m['y'] for m in marks)

    long_axis, short_axis = ('x', 'y') if span_x >= span_y else ('y', 'x')

    by_short = sorted(marks, key=lambda m: m[short_axis])
    low_group = sorted(by_short[:2], key=lambda m: m[long_axis], reverse=True)
    high_group = sorted(by_short[2:], key=lambda m: m[long_axis], reverse=True)

    # (0,2)=high 그룹 장변, (1,3)=low 그룹 장변, (0,1)/(2,3)=단변, (0,3)/(1,2)=대각선
    return [high_group[0], low_group[0], high_group[1], low_group[1]]


class PlatePoseDataset:
    """plate_pose_calc 디렉터리 하나를 대상으로 하는 읽기 전용 데이터셋."""

    def __init__(self):
        self.root: Optional[Path] = None
        self.records: List[PlateRecord] = []
        self.pallet: Optional[str] = None
        self.variant: str = VARIANT_CORRECTED

    @staticmethod
    def default_root() -> Path:
        """패키지 data 디렉터리 아래의 기본 데이터셋 경로 (존재 여부는 보장하지 않는다)."""
        from .. import paths
        return paths.DATA_DIR / DATASET_DIR_NAME

    def set_root(self, root_path) -> bool:
        """데이터셋 루트를 지정한다. 팔레트 하위 폴더가 하나도 없으면 실패."""
        root = Path(root_path)
        if not root.is_dir():
            return False
        self.root = root
        return bool(self.list_pallets())

    def list_pallets(self) -> List[str]:
        """루트 아래 팔레트 폴더 이름 목록(정렬)."""
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
        """한 팔레트의 YAML 전부를 읽어 records 를 채운다.

        Returns:
            (성공 여부, 사람이 읽는 메시지). 실패해도 예외를 올리지 않는다.
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
        """YAML 한 개를 PlateRecord 로. 스키마가 어긋나면 None (호출자가 건너뛴다)."""
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
        """jig 하나의 축별 시계열. jig_index 는 0..3."""
        if not 0 <= jig_index < len(JIG_KEYS):
            return {axis: [] for axis in POSE_AXES}
        return {
            axis: [r.jigs[jig_index][axis] for r in self.records]
            for axis in POSE_AXES
        }

    def jig_deviation_series(self, jig_index: int) -> Dict[str, List[float]]:
        """축별 평균 대비 편차. 재현성 산점도는 이 값을 그려야 μm 급 산포가 보인다.

        회전축은 ±180 경계를 넘나들므로 `LandmarkAnalyzer` 의 원형 통계를 쓴다
        (산술 차이는 179.9 와 -179.9 를 359.8 도 차이로 만든다).
        """
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
        """jig 하나의 축별 μ·σ·3σ·min·max.

        위치축(x/y/z) 은 `PrecisionTestManager` 의 통계를 그대로 쓴다.
        회전축은 그 산술 통계가 ±180 경계에서 무너지므로(179.9 와 -179.9 의 평균이 0)
        `LandmarkAnalyzer` 의 원형 평균·표준편차로 대체한다. 두 경우 모두 기존 자산이다.
        """
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

            # 회전축의 min/max 는 원값이 ±180 을 넘나들 수 있어 평균+편차로 되돌린다.
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
        """jig1~4 전체의 축별 통계를 한 리스트로."""
        rows: List[AxisStat] = []
        for jig_index in range(len(JIG_KEYS)):
            rows.extend(self.jig_statistics(jig_index))
        return rows

    def mean_marks(self) -> List[Dict[str, float]]:
        """로드된 전 파일에 걸친 jig 평균 좌표 4개 — 형상 검사의 대표값."""
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
        """대표 좌표를 실은 `JigPlateValidator`. 4개가 아니면 None."""
        target_marks = marks if marks is not None else self.mean_marks()
        if len(target_marks) != 4:
            return None

        validator = JigPlateValidator()
        if not validator.load_from_dicts(target_marks):
            return None
        return validator

    def geometry_report(self, marks: Optional[List[Dict[str, float]]] = None):
        """(변 길이 dict, ValidationResult 리스트). 검사기가 없으면 ({}, [])."""
        validator = self.build_validator(marks)
        if validator is None:
            return {}, []

        results = validator.check_rectangle() + validator.check_z_consistency()
        return validator.get_side_lengths(), results
