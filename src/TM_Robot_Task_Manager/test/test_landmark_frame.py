"""tools/landmark_frame 좌표 변환(rz_only/full·툴 오프셋·원형 평균)과 job_executor 랜드마크 프레임 job 을 검증한다."""
import math

import numpy as np
import pytest
from unittest.mock import MagicMock

from tm_task_manager.job_executor import JobExecutor
from tm_task_manager.recipe_manager import Job, RecipeManager
from tm_task_manager.tools.landmark_frame import (
    FRAME_MODE_FULL, FRAME_MODE_RZ_ONLY,
    landmark_frame_rotation, pose_from_landmark_frame, pose_in_landmark_frame)


LM = {'x': 198.446, 'y': 473.0, 'z': 11.43,
      'rx': 179.30, 'ry': 1.71, 'rz': -178.48, 'detected': True}

MARKS = {
    '1사분면': (58.471, 222.071, 29.967),
    '2사분면': (-78.716, 222.719, 30.147),
    '3사분면': (-79.203, 418.754, 33.078),
    '4사분면': (58.241, 418.342, 31.485),
}


def _job(**params):
    p = {'frame_mode': FRAME_MODE_RZ_ONLY, 'offset_x': 0.0, 'offset_y': 0.0,
         'offset_z': 0.0, 'offset_rx': 180.0, 'offset_ry': 0.0, 'offset_rz': 0.0,
         'velocity': 10.0}
    p.update(params)
    return Job(job_id=1, job_type='move_to_landmark_pose', params=p)


@pytest.fixture
def executor():
    node = MagicMock()
    node.current_base_name = 'RobotBase'
    ex = JobExecutor(ros_node=node)
    ex.logs = []
    ex.on_log = ex.logs.append
    ex.tm_landmark_pose = dict(LM)
    ex.moved = []
    ex._move_pose_keep = lambda label, target, *a: (ex.moved.append((label, target)) or True)
    ex._read_tcp_or_log = lambda label: [271.63, 695.62, -18.53, 178.63, 0.9, 0.53]
    return ex


def _logs(ex):
    return "\n".join(ex.logs)


def test_rz_only_ignores_marker_rx_ry():
    rel = {'x': 100.0, 'y': -50.0, 'z': 250.0, 'rx': 180.0, 'ry': 0.0, 'rz': 0.0}
    a = pose_from_landmark_frame(LM, rel, FRAME_MODE_RZ_ONLY)
    noisy = dict(LM, rx=LM['rx'] + 0.5, ry=LM['ry'] - 0.4)
    b = pose_from_landmark_frame(noisy, rel, FRAME_MODE_RZ_ONLY)
    for k in ('x', 'y', 'z', 'rx', 'ry', 'rz'):
        assert a[k] == pytest.approx(b[k], abs=1e-9)


def test_full_mode_does_follow_marker_rx_ry():
    rel = {'x': 100.0, 'y': -50.0, 'z': 250.0, 'rx': 180.0, 'ry': 0.0, 'rz': 0.0}
    a = pose_from_landmark_frame(LM, rel, FRAME_MODE_FULL)
    noisy = dict(LM, rx=LM['rx'] + 0.5, ry=LM['ry'] - 0.4)
    b = pose_from_landmark_frame(noisy, rel, FRAME_MODE_FULL)
    moved = math.dist((a['x'], a['y'], a['z']), (b['x'], b['y'], b['z']))
    assert moved > 1.0, f"full 모드인데 마커 자세 변화를 안 따라감 ({moved:.4f}mm)"


@pytest.mark.parametrize('mode', [FRAME_MODE_RZ_ONLY, FRAME_MODE_FULL])
def test_round_trip(mode):
    rel = {'x': 58.471, 'y': 222.071, 'z': 29.967, 'rx': -2.228, 'ry': -2.682, 'rz': -178.497}
    back = pose_in_landmark_frame(LM, pose_from_landmark_frame(LM, rel, mode), mode)
    for k in ('x', 'y', 'z'):
        assert back[k] == pytest.approx(rel[k], abs=1e-6)


def test_zero_offset_lands_on_the_marker():
    p = pose_from_landmark_frame(LM, {'x': 0, 'y': 0, 'z': 0}, FRAME_MODE_RZ_ONLY)
    assert (p['x'], p['y'], p['z']) == pytest.approx((LM['x'], LM['y'], LM['z']))


def test_rz_only_rotation_is_pure_yaw():
    R = landmark_frame_rotation(LM, FRAME_MODE_RZ_ONLY)
    assert R[2, 0] == pytest.approx(0.0)
    assert R[2, 1] == pytest.approx(0.0)
    assert R[2, 2] == pytest.approx(1.0)
    assert np.linalg.det(R) == pytest.approx(1.0)


def test_unknown_frame_mode_raises():
    with pytest.raises(ValueError):
        landmark_frame_rotation(LM, 'bogus')


def test_marker_rotation_carries_the_four_marks_rigidly():
    def pts(lm):
        return np.array([[pose_from_landmark_frame(lm, dict(zip('xyz', v)), FRAME_MODE_RZ_ONLY)[k]
                          for k in ('x', 'y', 'z')] for v in MARKS.values()])
    a, b = pts(LM), pts(dict(LM, rz=LM['rz'] + 35.0, x=LM['x'] + 120.0))
    import itertools
    for i, j in itertools.combinations(range(4), 2):
        assert np.linalg.norm(b[i] - b[j]) == pytest.approx(np.linalg.norm(a[i] - a[j]), abs=1e-9)


def test_job_type_is_registered():
    spec = RecipeManager.JOB_TYPES['move_to_landmark_pose']
    assert spec['category'] == 'Landmark'
    assert spec['params']['frame_mode']['choices'] == ['rz_only', 'full']
    assert spec['params']['frame_mode']['default'] == 'rz_only'
    for k in ('offset_x', 'offset_y', 'offset_z', 'offset_rx', 'offset_ry', 'offset_rz'):
        assert spec['params'][k]['type'] == 'float'


def test_dispatch_and_target(executor):
    assert executor._execute_job(_job(offset_x=58.471, offset_y=222.071, offset_z=29.967)) is True
    label, target = executor.moved[0]
    assert label == '마커 좌표계 이동'
    expect = pose_from_landmark_frame(
        LM, {'x': 58.471, 'y': 222.071, 'z': 29.967, 'rx': 180.0, 'ry': 0.0, 'rz': 0.0},
        FRAME_MODE_RZ_ONLY)
    for k in ('x', 'y', 'z'):
        assert target[k] == pytest.approx(expect[k])


def test_no_scan_fails(executor):
    executor.tm_landmark_pose = None
    assert executor._exec_move_to_landmark_pose(_job()) is False
    assert 'scan_tm_landmark 를 먼저 실행' in _logs(executor)
    assert executor.moved == []


def test_bad_frame_mode_fails(executor):
    assert executor._exec_move_to_landmark_pose(_job(frame_mode='sideways')) is False
    assert '알 수 없는 frame_mode' in _logs(executor)
    assert executor.moved == []


def test_non_robot_base_refused(executor):
    executor.ros_node.current_base_name = 'vision_TM_Landmark_detection'
    assert executor._exec_move_to_landmark_pose(_job()) is False
    assert executor.moved == []


def test_max_radius_guard(executor):
    assert executor._exec_move_to_landmark_pose(
        _job(offset_x=300.0, max_radius_mm=200.0)) is False
    assert '상한' in _logs(executor)
    assert executor.moved == []

    assert executor._exec_move_to_landmark_pose(
        _job(offset_x=100.0, max_radius_mm=200.0)) is True


def test_max_radius_zero_means_unlimited(executor):
    assert executor._exec_move_to_landmark_pose(
        _job(offset_x=5000.0, max_radius_mm=0.0)) is True


def test_teach_inverts_current_tcp(executor):
    offset, msg = executor.estimate_landmark_frame_target(_job().params)
    assert offset is not None, msg
    back = pose_from_landmark_frame(executor.tm_landmark_pose, offset, FRAME_MODE_RZ_ONLY)
    assert (back['x'], back['y'], back['z']) == pytest.approx((271.63, 695.62, -18.53), abs=1e-6)


def test_teach_without_scan_reports(executor):
    executor.tm_landmark_pose = None
    offset, msg = executor.estimate_landmark_frame_target(_job().params)
    assert offset is None
    assert 'scan_tm_landmark' in msg


def test_tool_offset_params_registered():
    p = RecipeManager.JOB_TYPES['move_to_landmark_pose']['params']
    for k in ('x', 'y', 'z', 'rx', 'ry', 'rz'):
        assert p[f'tool_offset_{k}']['type'] == 'float'
        assert p[f'tool_offset_{k}']['default'] == 0.0


def test_zero_tool_offset_changes_nothing(executor):
    executor._exec_move_to_landmark_pose(_job(offset_x=50.0, offset_z=-30.0))
    a = executor.moved[-1][1]
    executor._exec_move_to_landmark_pose(
        _job(offset_x=50.0, offset_z=-30.0, tool_offset_x=0.0, tool_offset_y=0.0))
    b = executor.moved[-1][1]
    for k in ('x', 'y', 'z', 'rx', 'ry', 'rz'):
        assert a[k] == pytest.approx(b[k])


def test_tool_offset_shifts_the_target(executor):
    executor._exec_move_to_landmark_pose(_job(offset_x=50.0, offset_z=-30.0))
    base = executor.moved[-1][1]
    executor._exec_move_to_landmark_pose(
        _job(offset_x=50.0, offset_z=-30.0, tool_offset_x=3.0, tool_offset_y=-2.0))
    shifted = executor.moved[-1][1]
    d = math.dist((base['x'], base['y'], base['z']), (shifted['x'], shifted['y'], shifted['z']))
    assert d == pytest.approx(math.hypot(3.0, 2.0), abs=1e-6)


def test_teach_fills_tool_offset_not_the_target(executor):
    params = _job(offset_x=57.597, offset_y=-222.473, offset_z=-28.647,
                  offset_rx=178.63, offset_ry=0.9, offset_rz=178.536).params
    offset, msg = executor.estimate_landmark_frame_tool_offset(params)
    assert offset is not None, msg
    assert set(offset) == {'x', 'y', 'z', 'rx', 'ry', 'rz'}

    executor._exec_move_to_landmark_pose(
        _job(**{**{k: v for k, v in params.items()},
                **{f'tool_offset_{k}': offset[k] for k in offset}}))
    t = executor.moved[-1][1]
    residual = np.array([t['x'] - 271.63, t['y'] - 695.62, t['z'] - (-18.53)])

    from scipy.spatial.transform import Rotation as _R
    tool_z = _R.from_euler('ZYX', [t['rz'], t['ry'], t['rx']], degrees=True).as_matrix()[:, 2]
    perp = np.linalg.norm(np.cross(residual, tool_z))
    assert perp < 1e-3, f"공구 Z 밖 잔차 {perp:.6f}mm — XY 재현이 안 됨"


def test_teach_is_idempotent(executor):
    base = _job(offset_x=57.597, offset_y=-222.473, offset_z=-28.647).params
    first, _ = executor.estimate_landmark_frame_tool_offset(base)
    loaded = dict(base, **{f'tool_offset_{k}': first[k] for k in first})
    second, _ = executor.estimate_landmark_frame_tool_offset(loaded)
    for k in first:
        assert second[k] == pytest.approx(first[k], abs=1e-6)


def _write_landmark_file(directory, name, pose):
    directory.mkdir(parents=True, exist_ok=True)
    import yaml as _yaml
    (directory / name).write_text(
        _yaml.safe_dump({'operator': 'jjh', 'landmark': pose}, allow_unicode=True),
        encoding='utf-8')


def test_landmark_source_params_registered():
    p = RecipeManager.JOB_TYPES['move_to_landmark_pose']['params']
    assert p['landmark_source']['choices'] == ['latest_scan', 'file']
    assert p['landmark_source']['default'] == 'latest_scan'
    assert p['source_path']['type'] == 'dirpath'
    assert p['average_count']['type'] == 'int'


def test_source_file_reads_and_averages(executor, tmp_path):
    d = tmp_path / 'lp'
    _write_landmark_file(d, 'a_20260815_100000.yaml', dict(LM, x=100.0))
    _write_landmark_file(d, 'a_20260815_100100.yaml', dict(LM, x=200.0))

    ok = executor._exec_move_to_landmark_pose(
        _job(landmark_source='file', source_path=str(d), file_prefix='a_', average_count=2))
    assert ok is True
    assert '2개 파일 평균' in _logs(executor)
    executor.moved.clear()
    executor._exec_move_to_landmark_pose(
        _job(landmark_source='file', source_path=str(d), file_prefix='a_', average_count=2,
             offset_x=0.0, offset_y=0.0, offset_z=0.0))
    assert executor.moved[-1][1]['x'] == pytest.approx(150.0)


def test_source_file_ignores_latest_scan(executor, tmp_path):
    d = tmp_path / 'lp'
    _write_landmark_file(d, 'a_20260815_100000.yaml', dict(LM, x=999.0))
    executor.tm_landmark_pose = dict(LM, x=1.0)

    executor._exec_move_to_landmark_pose(
        _job(landmark_source='file', source_path=str(d), file_prefix='a_', average_count=1))
    assert executor.moved[-1][1]['x'] == pytest.approx(999.0)


def test_source_file_works_without_any_scan(executor, tmp_path):
    d = tmp_path / 'lp'
    _write_landmark_file(d, 'a_20260815_100000.yaml', dict(LM))
    executor.tm_landmark_pose = None

    assert executor._exec_move_to_landmark_pose(
        _job(landmark_source='file', source_path=str(d), file_prefix='a_')) is True


def test_source_file_missing_folder_fails(executor, tmp_path):
    assert executor._exec_move_to_landmark_pose(
        _job(landmark_source='file', source_path=str(tmp_path / 'nope'))) is False
    assert '불러올 landmark_pose 파일이 없습니다' in _logs(executor)


def test_source_file_skips_broken_and_reports(executor, tmp_path):
    d = tmp_path / 'lp'
    _write_landmark_file(d, 'a_20260815_100000.yaml', dict(LM))
    (d / 'a_20260815_100100.yaml').write_text('landmark: {x: 1.0}\n', encoding='utf-8')

    assert executor._exec_move_to_landmark_pose(
        _job(landmark_source='file', source_path=str(d), file_prefix='a_', average_count=2)) is True
    assert 'landmark 불완전' in _logs(executor)
    assert '1개 파일 평균' in _logs(executor)


def test_unknown_source_fails(executor):
    assert executor._exec_move_to_landmark_pose(_job(landmark_source='telepathy')) is False
    assert '알 수 없는 landmark_source' in _logs(executor)


def test_tool_offset_z_moves_along_tool_axis(executor):
    from scipy.spatial.transform import Rotation as _R
    executor._exec_move_to_landmark_pose(_job(offset_x=50.0, offset_z=-30.0))
    base = executor.moved[-1][1]
    executor._exec_move_to_landmark_pose(
        _job(offset_x=50.0, offset_z=-30.0, tool_offset_z=12.0))
    shifted = executor.moved[-1][1]

    d = np.array([shifted[k] - base[k] for k in ('x', 'y', 'z')])
    tool_z = _R.from_euler(
        'ZYX', [base['rz'], base['ry'], base['rx']], degrees=True).as_matrix()[:, 2]
    assert np.linalg.norm(d) == pytest.approx(12.0, abs=1e-6)
    assert np.dot(d / np.linalg.norm(d), tool_z) == pytest.approx(1.0, abs=1e-9)


def test_offset_z_sign_is_robot_up_in_rz_only():
    up = pose_from_landmark_frame(LM, {'x': 0, 'y': 0, 'z': 100.0}, FRAME_MODE_RZ_ONLY)
    down = pose_from_landmark_frame(LM, {'x': 0, 'y': 0, 'z': -100.0}, FRAME_MODE_RZ_ONLY)
    assert up['z'] == pytest.approx(LM['z'] + 100.0)
    assert down['z'] == pytest.approx(LM['z'] - 100.0)
    assert (up['x'], up['y']) == pytest.approx((LM['x'], LM['y']))


def test_circular_mean_survives_180_wrap():
    from tm_task_manager.services.landmark_analyzer import LandmarkAnalyzer
    a = LandmarkAnalyzer()
    samples = [179.92, -179.88, 179.96, -179.95, 179.90,
               -179.97, 179.94, -179.91, 179.98, -179.93]
    for v in samples:
        a.add_measurement(1.0, 2.0, 3.0, v, 0.5, v)

    assert abs(np.mean(samples)) < 1.0, "표본이 경계를 걸치는지 확인 (산술평균 ≈ 0)"
    for method in ('none', '3sigma', 'iqr'):
        r = a.analyze(method, 'xyz_rx_ry_rz')
        assert abs(abs(r['mean']['rz']) - 180.0) < 0.05, f"{method}: {r['mean']['rz']}"
        assert r['count_after_outlier'] == 10, f"{method}: 정상 측정이 걸러짐"
        assert r['std']['rz'] < 0.2, f"{method}: 경계에서 std 가 부풀었다"


def test_circular_mean_matches_plain_mean_away_from_wrap():
    from tm_task_manager.services.landmark_analyzer import LandmarkAnalyzer
    a = LandmarkAnalyzer()
    samples = [89.78, 89.92, 89.74, 90.01, 89.86]
    for v in samples:
        a.add_measurement(1.0, 2.0, 3.0, 0.0, 0.0, v)
    r = a.analyze('none', 'xyz_rx_ry_rz')
    assert r['mean']['rz'] == pytest.approx(float(np.mean(samples)), abs=1e-6)
    assert r['std']['rz'] == pytest.approx(float(np.std(samples)), abs=1e-6)


def test_xyz_mean_is_untouched():
    from tm_task_manager.services.landmark_analyzer import LandmarkAnalyzer
    a = LandmarkAnalyzer()
    for v in (10.0, 12.0, 14.0):
        a.add_measurement(v, v * 2, v * 3, 179.9, 0.0, -179.9)
    r = a.analyze('none', 'xyz_rx_ry_rz')
    assert (r['mean']['x'], r['mean']['y'], r['mean']['z']) == pytest.approx((12.0, 24.0, 36.0))


def test_teaching_pose_reproduces_exactly():
    LM_T = {'x': 209.116307, 'y': 532.93503, 'z': 11.842066549999998,
            'rx': 179.807403, 'ry': 1.27104361, 'rz': -179.448196}
    taught = {'x': 217.34, 'y': 778.17, 'z': -130.38,
              'rx': 179.96, 'ry': -0.06, 'rz': -89.51}
    off = pose_in_landmark_frame(LM_T, taught, FRAME_MODE_RZ_ONLY)
    assert (off['x'], off['y'], off['z']) == pytest.approx(
        (-10.585, -245.144, -142.222), abs=1e-3)
    assert off['rz'] == pytest.approx(89.938, abs=1e-3), "마커 긴변에서 90도 = 그리퍼 방향"

    back = pose_from_landmark_frame(LM_T, off, FRAME_MODE_RZ_ONLY)
    for k in ('x', 'y', 'z', 'rx', 'ry', 'rz'):
        assert back[k] == pytest.approx(taught[k], abs=1e-6)
