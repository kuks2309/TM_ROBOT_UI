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
    file_name: str
    saved_at: str
    plate_pose: Dict[str, float]
    jigs: List[Dict[str, float]]


@dataclass
class AxisStat:
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
        if not 0 <= jig_index < len(JIG_KEYS):
            return {axis: [] for axis in POSE_AXES}
        return {
            axis: [r.jigs[jig_index][axis] for r in self.records]
            for axis in POSE_AXES
        }

    def jig_deviation_series(self, jig_index: int) -> Dict[str, List[float]]:
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
        target_marks = marks if marks is not None else self.mean_marks()
        if len(target_marks) != 4:
            return None

        validator = JigPlateValidator()
        if not validator.load_from_dicts(target_marks):
            return None
        return validator

    def geometry_report(self, marks: Optional[List[Dict[str, float]]] = None):
        validator = self.build_validator(marks)
        if validator is None:
            return {}, []

        results = validator.check_rectangle() + validator.check_z_consistency()
        return validator.get_side_lengths(), results
