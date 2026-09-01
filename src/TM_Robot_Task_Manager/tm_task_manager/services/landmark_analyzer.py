"""랜드마크 반복 측정 통계 — outlier 제거(IQR/3σ)와 원형 각도 평균.

각도(rx/ry/rz, deg)는 ±180° 랩어라운드 때문에 산술 통계 대신 원형
(circular) 평균·편차를 쓴다.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
import numpy as np


@dataclass
class LandmarkMeasurement:
    """측정 1건 (x/y/z mm, rx/ry/rz deg, 기록 시각)."""
    x: float
    y: float
    z: float
    rx: float
    ry: float
    rz: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


ANGLE_COLUMNS = ('rx', 'ry', 'rz')


def circular_mean_deg(values) -> float:
    """atan2 기반 원형 평균(deg) — 179°와 -179°의 평균이 180° 근방이 되게 한다."""
    if len(values) == 0:
        return 0.0
    radians = np.deg2rad(np.asarray(values, dtype=float))
    return float(np.rad2deg(np.arctan2(np.mean(np.sin(radians)), np.mean(np.cos(radians)))))


def angle_deviation_deg(values, center: float) -> np.ndarray:
    """center 기준 편차를 ±180° 범위로 정규화해 돌려준다 (deg)."""
    delta = np.asarray(values, dtype=float) - center
    return (delta + 180.0) % 360.0 - 180.0


def circular_std_deg(values) -> float:
    """원형 평균 기준 편차의 표준편차(deg)."""
    if len(values) == 0:
        return 0.0
    return float(np.std(angle_deviation_deg(values, circular_mean_deg(values))))


class LandmarkAnalyzer:
    """측정 축적 → outlier 제거 → 평균/표준편차 → 최종 pose 산출기."""

    # _get_values_array 6열 배열에서 이 인덱스부터가 각도 열 (원형 통계 적용 대상)
    ANGLE_COLUMN_START = 3

    def __init__(self):
        self.measurements: List[LandmarkMeasurement] = []

    def reset(self) -> None:
        self.measurements = []

    def add_measurement(self, x: float, y: float, z: float,
                        rx: float, ry: float, rz: float) -> None:
        """측정 1건(mm/deg)을 타임스탬프와 함께 추가한다."""
        measurement = LandmarkMeasurement(x=x, y=y, z=z, rx=rx, ry=ry, rz=rz)
        self.measurements.append(measurement)

    def _get_values_array(self, target: str = 'xyz') -> np.ndarray:
        if not self.measurements:
            return np.array([])

        if target == 'xyz':
            return np.array([[m.x, m.y, m.z] for m in self.measurements])
        else:
            return np.array([[m.x, m.y, m.z, m.rx, m.ry, m.rz] for m in self.measurements])

    def _filter_by_mask(self, mask: np.ndarray) -> List[LandmarkMeasurement]:
        return [m for m, keep in zip(self.measurements, mask) if keep]

    def remove_outliers_iqr(self, target: str = 'xyz') -> List[LandmarkMeasurement]:
        """열별 IQR 1.5배 필터 — 4건 미만은 사분위가 무의미해 전체 통과."""
        if len(self.measurements) < 4:
            return self.measurements.copy()

        values = self._get_values_array(target)
        n_cols = values.shape[1]

        mask = np.ones(len(self.measurements), dtype=bool)
        for col in range(n_cols):
            col_data = values[:, col]
            if col >= self.ANGLE_COLUMN_START:
                col_data = angle_deviation_deg(col_data, circular_mean_deg(col_data))
            q1 = np.percentile(col_data, 25)
            q3 = np.percentile(col_data, 75)
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            mask &= (col_data >= lower) & (col_data <= upper)

        return self._filter_by_mask(mask)

    def remove_outliers_3sigma(self, target: str = 'xyz') -> List[LandmarkMeasurement]:
        """열별 3σ 필터 — 3건 미만은 표준편차가 무의미해 전체 통과."""
        if len(self.measurements) < 3:
            return self.measurements.copy()

        values = self._get_values_array(target)
        n_cols = values.shape[1]

        mask = np.ones(len(self.measurements), dtype=bool)
        for col in range(n_cols):
            col_data = values[:, col]
            if col >= self.ANGLE_COLUMN_START:
                col_data = angle_deviation_deg(col_data, circular_mean_deg(col_data))
            mean = np.mean(col_data)
            std = np.std(col_data)
            if std > 0:
                lower = mean - 3 * std
                upper = mean + 3 * std
                mask &= (col_data >= lower) & (col_data <= upper)

        return self._filter_by_mask(mask)

    def analyze(self, method: str = 'none', target: str = 'xyz') -> Dict:
        """outlier 제거 후 6축 평균·표준편차를 계산한다.

        target 은 outlier 필터 적용 범위만 정한다 ('xyz'=위치 3열만 필터) —
        반환 mean/std 는 항상 6축 전부이며, 'xyz' 일 때 각도 outlier 는 남은 채
        평균된다. 각도 통계는 원형(circular) 계산.
        """
        count_original = len(self.measurements)

        if method == 'iqr':
            filtered = self.remove_outliers_iqr(target)
        elif method == '3sigma':
            filtered = self.remove_outliers_3sigma(target)
        else:
            filtered = self.measurements.copy()

        count_after = len(filtered)

        if not filtered:
            return {
                'mean': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'rx': 0.0, 'ry': 0.0, 'rz': 0.0},
                'std': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'rx': 0.0, 'ry': 0.0, 'rz': 0.0},
                'count_original': count_original,
                'count_after_outlier': 0,
                'outliers_removed': count_original
            }

        x_vals = [m.x for m in filtered]
        y_vals = [m.y for m in filtered]
        z_vals = [m.z for m in filtered]
        rx_vals = [m.rx for m in filtered]
        ry_vals = [m.ry for m in filtered]
        rz_vals = [m.rz for m in filtered]

        return {
            'mean': {
                'x': float(np.mean(x_vals)),
                'y': float(np.mean(y_vals)),
                'z': float(np.mean(z_vals)),
                'rx': circular_mean_deg(rx_vals),
                'ry': circular_mean_deg(ry_vals),
                'rz': circular_mean_deg(rz_vals)
            },
            'std': {
                'x': float(np.std(x_vals)),
                'y': float(np.std(y_vals)),
                'z': float(np.std(z_vals)),
                'rx': circular_std_deg(rx_vals),
                'ry': circular_std_deg(ry_vals),
                'rz': circular_std_deg(rz_vals)
            },
            'count_original': count_original,
            'count_after_outlier': count_after,
            'outliers_removed': count_original - count_after
        }

    def get_final_pose(self, method: str = 'none', target: str = 'xyz') -> Dict:
        """평균 pose dict(detected 포함) — 유효 측정 0건이면 detected=False."""
        analysis = self.analyze(method, target)
        mean = analysis['mean']

        if analysis['count_after_outlier'] == 0:
            return {'x': 0.0, 'y': 0.0, 'z': 0.0, 'rx': 0.0, 'ry': 0.0, 'rz': 0.0, 'detected': False}

        return {
            'x': mean['x'],
            'y': mean['y'],
            'z': mean['z'],
            'rx': mean['rx'],
            'ry': mean['ry'],
            'rz': mean['rz'],
            'detected': True
        }
