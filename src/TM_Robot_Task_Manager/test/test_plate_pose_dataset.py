#!/usr/bin/env python3
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tm_task_manager.services.plate_pose_dataset import (
    JIG_KEYS,
    VARIANT_CORRECTED,
    VARIANT_RAW,
    PlatePoseDataset,
    normalize_jig_order,
)

RAW_PALLET0 = [
    {'x': 491.311, 'y': 152.674, 'z': -295.904, 'rx': 179.548, 'ry': -0.300, 'rz': 90.039},
    {'x': 295.205, 'y': 153.258, 'z': -294.544, 'rx': -179.884, 'ry': -0.361, 'rz': 90.052},
    {'x': 490.627, 'y': 290.182, 'z': -299.674, 'rx': -177.279, 'ry': -0.159, 'rz': 89.810},
    {'x': 294.083, 'y': 290.424, 'z': -298.264, 'rx': -179.494, 'ry': -0.311, 'rz': 90.117},
]
EXPECTED_XY_ORDER = [
    (490.627, 290.182),
    (491.311, 152.674),
    (294.083, 290.424),
    (295.205, 153.258),
]


def _xy(marks):
    return [(m['x'], m['y']) for m in marks]


def _write_yaml(directory: Path, name: str, marks, saved_at='2026-08-19 11:11:17'):
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        'operator': 'test',
        'recipe': 'pallet0_cali',
        'task_caption': 'pallet_plate_pose_calc',
        'saved_at': saved_at,
        'plate_pose': {'x': 392.807, 'y': 221.635, 'z': -297.096,
                       'rx': 0.418, 'ry': 1.562, 'rz': 90.377},
        'landmarks': {
            key: dict(mark, measured_at=saved_at)
            for key, mark in zip(JIG_KEYS, marks)
        },
    }
    path = directory / name
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(payload, f)
    return path


@pytest.fixture
def dataset_root(tmp_path):
    root = tmp_path / 'plate_pose_calc'
    pallet0 = root / 'pallet0'

    shifted = [dict(m, x=m['x'] + 0.004) for m in RAW_PALLET0]
    _write_yaml(pallet0, 'p0_a.yaml', RAW_PALLET0)
    _write_yaml(pallet0, 'p0_b.yaml', shifted)

    corrected_order = normalize_jig_order(RAW_PALLET0)
    _write_yaml(pallet0 / 'corrected', 'p0_a.corrected.yaml', corrected_order)
    _write_yaml(pallet0 / 'corrected', 'p0_b.corrected.yaml', normalize_jig_order(shifted))

    _write_yaml(root / 'pallet1', 'p1_a.yaml', RAW_PALLET0)
    return root


class TestNormalizeJigOrder:
    def test_raw_is_reordered_to_convention(self):
        assert _xy(normalize_jig_order(RAW_PALLET0)) == EXPECTED_XY_ORDER

    def test_is_idempotent(self):
        once = normalize_jig_order(RAW_PALLET0)
        assert _xy(normalize_jig_order(once)) == _xy(once)

    def test_long_side_lands_on_index_0_2(self):
        m = normalize_jig_order(RAW_PALLET0)
        long_side = abs(m[0]['x'] - m[2]['x'])
        short_side = abs(m[0]['y'] - m[1]['y'])
        assert long_side > short_side

    def test_returns_input_unchanged_when_not_four(self):
        three = RAW_PALLET0[:3]
        assert normalize_jig_order(three) == three


class TestLoad:
    def test_lists_pallets(self, dataset_root):
        ds = PlatePoseDataset()
        assert ds.set_root(dataset_root) is True
        assert ds.list_pallets() == ['pallet0', 'pallet1']

    def test_set_root_rejects_missing_dir(self, tmp_path):
        ds = PlatePoseDataset()
        assert ds.set_root(tmp_path / 'nope') is False

    def test_loads_corrected_variant(self, dataset_root):
        ds = PlatePoseDataset()
        ds.set_root(dataset_root)
        ok, message = ds.load('pallet0', VARIANT_CORRECTED)
        assert ok is True
        assert len(ds.records) == 2
        assert '2개 로드' in message

    def test_corrected_glob_excludes_raw_files(self, dataset_root):
        ds = PlatePoseDataset()
        ds.set_root(dataset_root)
        ds.load('pallet0', VARIANT_CORRECTED)
        assert all(r.file_name.endswith('.corrected.yaml') for r in ds.records)

    def test_raw_glob_excludes_corrected_subdir(self, dataset_root):
        ds = PlatePoseDataset()
        ds.set_root(dataset_root)
        ds.load('pallet0', VARIANT_RAW)
        assert all(not r.file_name.endswith('.corrected.yaml') for r in ds.records)

    def test_raw_and_corrected_agree_after_normalization(self, dataset_root):
        ds_raw, ds_corr = PlatePoseDataset(), PlatePoseDataset()
        ds_raw.set_root(dataset_root)
        ds_corr.set_root(dataset_root)
        ds_raw.load('pallet0', VARIANT_RAW)
        ds_corr.load('pallet0', VARIANT_CORRECTED)
        assert _xy(ds_raw.records[0].jigs) == _xy(ds_corr.records[0].jigs)

    def test_missing_pallet_fails_without_raising(self, dataset_root):
        ds = PlatePoseDataset()
        ds.set_root(dataset_root)
        ok, message = ds.load('pallet9', VARIANT_RAW)
        assert ok is False
        assert 'YAML 파일이 없습니다' in message

    def test_malformed_file_is_skipped(self, dataset_root):
        (dataset_root / 'pallet1' / 'broken.yaml').write_text('landmarks: 3\n')
        ds = PlatePoseDataset()
        ds.set_root(dataset_root)
        ok, message = ds.load('pallet1', VARIANT_RAW)
        assert ok is True
        assert len(ds.records) == 1
        assert '건너뜀' in message


class TestStatistics:
    def test_series_length_matches_record_count(self, dataset_root):
        ds = PlatePoseDataset()
        ds.set_root(dataset_root)
        ds.load('pallet0', VARIANT_RAW)
        assert len(ds.jig_series(0)['x']) == 2

    def test_out_of_range_index_returns_empty(self, dataset_root):
        ds = PlatePoseDataset()
        ds.set_root(dataset_root)
        ds.load('pallet0', VARIANT_RAW)
        assert ds.jig_series(4)['x'] == []

    def test_statistics_cover_all_axes_for_all_jigs(self, dataset_root):
        ds = PlatePoseDataset()
        ds.set_root(dataset_root)
        ds.load('pallet0', VARIANT_RAW)
        rows = ds.all_statistics()
        assert len(rows) == 24
        assert {r.target for r in rows} == set(JIG_KEYS)

    def test_sigma3_is_three_times_std(self, dataset_root):
        ds = PlatePoseDataset()
        ds.set_root(dataset_root)
        ds.load('pallet0', VARIANT_RAW)
        for row in ds.all_statistics():
            assert row.sigma3 == pytest.approx(3 * row.std)

    def test_range_is_max_minus_min(self, dataset_root):
        ds = PlatePoseDataset()
        ds.set_root(dataset_root)
        ds.load('pallet0', VARIANT_RAW)
        row = ds.all_statistics()[0]
        assert row.value_range == pytest.approx(row.maximum - row.minimum)


class TestCircularAxes:

    WRAPPED = [179.9, -179.9, 179.8, -179.8]

    @pytest.fixture
    def wrapped_root(self, tmp_path):
        root = tmp_path / 'plate_pose_calc'
        for index, rx in enumerate(self.WRAPPED):
            marks = [dict(m, rx=rx) for m in RAW_PALLET0]
            _write_yaml(root / 'pallet0', f'w_{index}.yaml', marks)
        return root

    def _stats(self, wrapped_root, axis):
        ds = PlatePoseDataset()
        ds.set_root(wrapped_root)
        ds.load('pallet0', VARIANT_RAW)
        return next(r for r in ds.jig_statistics(0) if r.axis == axis)

    def test_rotation_mean_uses_circular_statistics(self, wrapped_root):
        row = self._stats(wrapped_root, 'rx')
        assert abs(abs(row.mean) - 180.0) < 0.2

    def test_rotation_std_does_not_inflate_at_boundary(self, wrapped_root):
        row = self._stats(wrapped_root, 'rx')
        assert row.std < 0.2

    def test_rotation_min_max_stay_near_mean(self, wrapped_root):
        row = self._stats(wrapped_root, 'rx')
        assert row.value_range < 0.5

    def test_position_axis_unaffected(self, wrapped_root):
        row = self._stats(wrapped_root, 'x')
        assert row.mean == pytest.approx(EXPECTED_XY_ORDER[0][0])


class TestDeviationSeries:
    def test_deviation_is_centred_on_zero(self, dataset_root):
        ds = PlatePoseDataset()
        ds.set_root(dataset_root)
        ds.load('pallet0', VARIANT_RAW)
        deviations = ds.jig_deviation_series(0)
        assert sum(deviations['x']) == pytest.approx(0.0, abs=1e-9)

    def test_deviation_length_matches_records(self, dataset_root):
        ds = PlatePoseDataset()
        ds.set_root(dataset_root)
        ds.load('pallet0', VARIANT_RAW)
        assert len(ds.jig_deviation_series(0)['rz']) == 2

    def test_deviation_empty_without_data(self):
        assert PlatePoseDataset().jig_deviation_series(0)['x'] == []

    def test_rotation_deviation_wraps_shortest_way(self, tmp_path):
        root = tmp_path / 'plate_pose_calc'
        for index, rx in enumerate([179.9, -179.9]):
            _write_yaml(root / 'pallet0', f'w_{index}.yaml',
                        [dict(m, rx=rx) for m in RAW_PALLET0])
        ds = PlatePoseDataset()
        ds.set_root(root)
        ds.load('pallet0', VARIANT_RAW)
        deviations = ds.jig_deviation_series(0)['rx']
        assert max(abs(d) for d in deviations) < 0.2


class TestGeometry:
    def test_mean_marks_average_across_records(self, dataset_root):
        ds = PlatePoseDataset()
        ds.set_root(dataset_root)
        ds.load('pallet0', VARIANT_RAW)
        means = ds.mean_marks()
        assert len(means) == 4
        expected = (EXPECTED_XY_ORDER[0][0] + EXPECTED_XY_ORDER[0][0] + 0.004) / 2
        assert means[0]['x'] == pytest.approx(expected)

    def test_geometry_report_matches_known_pallet0_deviation(self, dataset_root):
        ds = PlatePoseDataset()
        ds.set_root(dataset_root)
        ds.load('pallet0', VARIANT_RAW)
        sides, results = ds.geometry_report()

        assert set(sides) == {'jig1-jig3', 'jig2-jig4', 'jig1-jig2',
                              'jig3-jig4', 'jig1-jig4', 'jig2-jig3'}
        assert sides['jig1-jig3'] == pytest.approx(196.55, abs=0.05)
        assert sides['jig1-jig2'] == pytest.approx(137.52, abs=0.05)

        diagonal = next(r for r in results if r.name == '대각선 차이')
        assert diagonal.value == pytest.approx(1.95, abs=0.05)
        assert diagonal.passed is False

    def test_geometry_report_empty_without_data(self):
        ds = PlatePoseDataset()
        assert ds.geometry_report() == ({}, [])

    def test_build_validator_returns_none_without_data(self):
        assert PlatePoseDataset().build_validator() is None
