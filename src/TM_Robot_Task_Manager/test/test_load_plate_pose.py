#!/usr/bin/env python3
"""job_executor load_plate_pose job(측정 YAML 로드·평균·rect 가드)을 검증한다."""
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tm_task_manager.job_executor import JobExecutor


def _marks(jig1_y, jig2_y, jig3_y, jig4_y, x_left=450.5, x_right=646.9, z=-325.0):
    return {
        'jig1': {'x': x_right, 'y': jig1_y, 'z': z, 'rx': 180.0, 'ry': 0.0, 'rz': 90.0},
        'jig2': {'x': x_left, 'y': jig2_y, 'z': z, 'rx': 180.0, 'ry': 0.0, 'rz': 90.0},
        'jig3': {'x': x_right, 'y': jig3_y, 'z': z, 'rx': 180.0, 'ry': 0.0, 'rz': 90.0},
        'jig4': {'x': x_left, 'y': jig4_y, 'z': z, 'rx': 180.0, 'ry': 0.0, 'rz': 90.0},
    }


def _write(dirpath, name, landmarks, plate_pose=None):
    payload = {
        'operator': 'test',
        'saved_at': '2026-08-14 10:00:00',
        'plate_pose': plate_pose or {'x': 0.0, 'y': 0.0, 'z': 0.0,
                                     'rx': 0.0, 'ry': 0.0, 'rz': 0.0},
        'landmarks': landmarks,
    }
    p = Path(dirpath) / name
    p.write_text(yaml.dump(payload, allow_unicode=True), encoding='utf-8')
    return p


class _Ex:

    def __init__(self, alarm=None):
        self.on_plate_rect_alarm = alarm
        self.detected_plate_pose = None
        self.jig_landmark_results = {}
        self.logs = []

    def _log(self, msg):
        self.logs.append(msg)

    _exec_load_plate_pose = JobExecutor._exec_load_plate_pose
    _resolve_plate_pose_files = JobExecutor._resolve_plate_pose_files
    _confirm_plate_rectangle = JobExecutor._confirm_plate_rectangle


class _Job:
    def __init__(self, **params):
        self.params = params
        self.type = 'load_plate_pose'
        self.id = 1


@pytest.fixture
def good_dir(tmp_path):
    _write(tmp_path, 'pallet0_cali_a_100000.yaml', _marks(-68.0, -68.0, 68.0, 68.0))
    _write(tmp_path, 'pallet0_cali_b_100100.yaml', _marks(-69.0, -69.0, 69.0, 69.0))
    _write(tmp_path, 'pallet0_cali_c_100200.yaml', _marks(-70.0, -70.0, 70.0, 70.0))
    return tmp_path


def test_empty_source_path_rejected():
    ex = _Ex()
    assert ex._exec_load_plate_pose(_Job(source_path='')) is False
    assert ex.detected_plate_pose is None


def test_missing_directory_rejected(tmp_path):
    ex = _Ex()
    assert ex._exec_load_plate_pose(_Job(source_path=str(tmp_path / 'nope'))) is False


def test_single_file_loads(good_dir):
    ex = _Ex()
    target = good_dir / 'pallet0_cali_b_100100.yaml'
    assert ex._exec_load_plate_pose(_Job(source_path=str(target))) is True
    assert ex.detected_plate_pose is not None
    assert ex.detected_plate_pose['y'] == pytest.approx(0.0, abs=1e-6)


def test_latest_file_chosen_when_average_count_is_one(good_dir):
    ex = _Ex()
    assert ex._exec_load_plate_pose(
        _Job(source_path=str(good_dir), file_prefix='pallet0_cali', average_count=1)) is True
    assert ex.jig_landmark_results[1]['y'] == pytest.approx(-70.0)


def test_average_of_all_files(good_dir):
    ex = _Ex()
    assert ex._exec_load_plate_pose(
        _Job(source_path=str(good_dir), file_prefix='pallet0_cali', average_count=0)) is True
    assert ex.jig_landmark_results[1]['y'] == pytest.approx(-69.0)
    assert ex.jig_landmark_results[3]['y'] == pytest.approx(+69.0)


def test_jig_landmark_results_restored_for_align_guard(good_dir):
    ex = _Ex()
    ex._exec_load_plate_pose(_Job(source_path=str(good_dir), average_count=0))
    assert set(ex.jig_landmark_results) == {1, 2, 3, 4}
    for mark in ex.jig_landmark_results.values():
        assert mark['detected'] is True
        for k in ('x', 'y', 'z', 'rx', 'ry', 'rz'):
            assert k in mark


def test_pose_recomputed_not_copied(tmp_path):
    _write(tmp_path, 'p_100000.yaml', _marks(-68.0, -68.0, 68.0, 68.0),
           plate_pose={'x': 9999.0, 'y': 9999.0, 'z': 9999.0,
                       'rx': 99.0, 'ry': 99.0, 'rz': 99.0})
    ex = _Ex()
    assert ex._exec_load_plate_pose(_Job(source_path=str(tmp_path))) is True
    assert ex.detected_plate_pose['x'] != pytest.approx(9999.0)
    assert ex.detected_plate_pose['x'] == pytest.approx((450.5 + 646.9) / 2)


def test_prefix_filter_excludes_other_pallets(tmp_path):
    _write(tmp_path, 'pallet0_cali_100000.yaml', _marks(-68.0, -68.0, 68.0, 68.0))
    _write(tmp_path, 'pallet5_cali_100100.yaml', _marks(-10.0, -10.0, 10.0, 10.0))
    ex = _Ex()
    ex._exec_load_plate_pose(
        _Job(source_path=str(tmp_path), file_prefix='pallet0_cali', average_count=0))
    assert ex.jig_landmark_results[1]['y'] == pytest.approx(-68.0)


def test_file_missing_jigs_is_skipped(tmp_path):
    _write(tmp_path, 'p_100000.yaml', _marks(-68.0, -68.0, 68.0, 68.0))
    bad = _marks(-99.0, -99.0, 99.0, 99.0)
    del bad['jig3']
    _write(tmp_path, 'p_100100.yaml', bad)
    ex = _Ex()
    assert ex._exec_load_plate_pose(_Job(source_path=str(tmp_path), average_count=0)) is True
    assert ex.jig_landmark_results[1]['y'] == pytest.approx(-68.0)
    assert any('건너뜁니다' in m for m in ex.logs)


def test_all_files_invalid_rejected(tmp_path):
    bad = _marks(-99.0, -99.0, 99.0, 99.0)
    del bad['jig2']
    _write(tmp_path, 'p_100000.yaml', bad)
    ex = _Ex()
    assert ex._exec_load_plate_pose(_Job(source_path=str(tmp_path))) is False
    assert ex.detected_plate_pose is None


def test_rect_guard_warns_but_does_not_block_on_load(tmp_path):
    _write(tmp_path, 'p_100000.yaml', _marks(-70.795, -68.767, 66.251, 65.044))
    ex = _Ex(alarm=lambda payload: pytest.fail("실행 단계인데 작업자에게 물었다"))
    assert ex._exec_load_plate_pose(
        _Job(source_path=str(tmp_path), max_side_diff_mm=1.0,
             max_diagonal_diff_mm=1.5, max_angle_error_deg=1.0)) is True
    assert any('[경고] 직사각형 검증 실패' in m for m in ex.logs)
    assert not any('[알람]' in m for m in ex.logs)
    assert ex.detected_plate_pose is not None


def test_rect_guard_can_be_disabled(tmp_path):
    _write(tmp_path, 'p_100000.yaml', _marks(-70.795, -68.767, 66.251, 65.044))
    ex = _Ex(alarm=lambda payload: pytest.fail("가드를 껐는데 물었다"))
    assert ex._exec_load_plate_pose(
        _Job(source_path=str(tmp_path), rect_guard_enabled=False)) is True
    assert ex.detected_plate_pose is not None
