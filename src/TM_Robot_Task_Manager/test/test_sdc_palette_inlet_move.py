"""job_executor sdc_palette_inlet_move job(마커 상대 입구 이동·offset 읽기·실패 조건)을 검증한다."""
import pytest
from unittest.mock import MagicMock, patch

from tm_task_manager.job_executor import JobExecutor
from tm_task_manager.recipe_manager import Job, RecipeManager
from tm_task_manager.services.config_manager import ConfigManager

CURRENT_TCP = [-950.0, -50.0, 600.0, 90.78, -23.03, -86.66]
MARKER = {'x': -1195.283, 'y': -103.21854, 'z': 738.9024,
          'rx': -90.78737, 'ry': -0.954692, 'rz': 93.685646}
ENTRY = {'description': '팔래트 입구 마커 frame 오프셋', 'type': 'marker_frame_offset',
         'values': [65.4, 220.74, -310.54]}
ALIGN_ENTRY = {'description': '정렬 offset', 'type': 'tcp_orientation_offset',
               'values': [0.0, -22.0, 0.0]}
INLET_TAUGHT = (-886.82, -14.21, 523.57)
YAML_OFFSET = [68.73, 243.08, -310.39]


def _expected_marker_orientation():
    import numpy as np
    from scipy.spatial.transform import Rotation

    R_m = Rotation.from_euler(
        'ZYX', [MARKER['rz'], MARKER['ry'], MARKER['rx']], degrees=True).as_matrix()
    R_a = Rotation.from_euler(
        'ZYX', [-MARKER['rz'] + 0.0, MARKER['ry'] - 22.0, -MARKER['rx'] + 0.0],
        degrees=True).as_matrix()
    z_m, z_a = R_m[:, 2], R_a[:, 2]
    axis = np.cross(z_a, z_m)
    s = float(np.linalg.norm(axis))
    c = float(np.dot(z_a, z_m))
    snap = Rotation.from_rotvec(axis / s * __import__('math').atan2(s, c)).as_matrix() \
        if s > 1e-12 else np.eye(3)
    rz, ry, rx = Rotation.from_matrix(snap @ R_a).as_euler('ZYX', degrees=True)
    return float(rx), float(ry), float(rz)


@pytest.fixture
def executor():
    node = MagicMock()
    node.current_tcp_pose = list(CURRENT_TCP)
    ex = JobExecutor(ros_node=node)
    ex.logs = []
    ex.on_log = ex.logs.append
    ex.detected_landmark_pose = dict(MARKER)
    return ex


def _job(**params):
    params.setdefault('wait_after_command', 0)
    return Job(job_id=1, job_type='sdc_palette_inlet_move', params=params)


def _logs(executor):
    return "\n".join(executor.logs)


def _patch_entry(entry, align_entry='default'):
    if align_entry == 'default':
        align_entry = dict(ALIGN_ENTRY)
    table = {'sdc_palette_inlet_move': entry, 'sdc_palette_tcp_align': align_entry}
    return patch.object(ConfigManager, 'get_position',
                        side_effect=lambda name: table.get(name))


def test_offset_entry_registered_in_yaml():
    entry = ConfigManager().get_position('sdc_palette_inlet_move')
    assert entry is not None
    assert entry['type'] == 'marker_frame_offset'
    assert entry['values'] == YAML_OFFSET


def test_job_type_is_registered():
    spec = RecipeManager.JOB_TYPES['sdc_palette_inlet_move']
    assert spec['name'] == 'sdc_palette_inlet_move'
    assert spec['category'] == 'Landmark'
    assert set(spec['params']) == {'dx', 'dy', 'dz', 'velocity', 'wait_after_command'}
    assert spec['params']['velocity']['default'] == 10.0
    assert spec['params']['dx']['default'] == 0.0
    assert spec['params']['dy']['default'] == 0.0
    assert spec['params']['dz']['default'] == 0.0


def test_dispatch_reaches_handler(executor):
    executor._move_to_position_line = MagicMock(return_value=(True, '이동 완료'))
    with _patch_entry(dict(ENTRY)):
        assert executor._execute_job(_job()) is True
    executor._move_to_position_line.assert_called_once()


def test_moves_to_marker_relative_inlet_with_marker_orientation(executor):
    executor._move_to_position_line = MagicMock(return_value=(True, '이동 완료'))

    with _patch_entry(dict(ENTRY)):
        assert executor._exec_sdc_palette_inlet_move(_job()) is True

    args = executor._move_to_position_line.call_args[0]
    assert args[0] == 'tcp'
    assert args[1] == pytest.approx(INLET_TAUGHT[0], abs=0.1)
    assert args[2] == pytest.approx(INLET_TAUGHT[1], abs=0.1)
    assert args[3] == pytest.approx(INLET_TAUGHT[2], abs=0.1)
    exp_rx, exp_ry, exp_rz = _expected_marker_orientation()
    assert args[4] == pytest.approx(exp_rx, abs=0.01)
    assert args[5] == pytest.approx(exp_ry, abs=0.01)
    assert args[6] == pytest.approx(exp_rz, abs=0.01)
    assert args[7] == 10.0
    assert 'sdc_palette_inlet_move 완료' in _logs(executor)


def test_fails_when_align_entry_missing(executor):
    executor._move_to_position_line = MagicMock()
    with _patch_entry(dict(ENTRY), align_entry=None):
        assert executor._exec_sdc_palette_inlet_move(_job()) is False
    executor._move_to_position_line.assert_not_called()
    assert '마커 자세 계산용' in _logs(executor)


def test_correction_params_shift_target_in_marker_frame(executor):
    import numpy as np
    from scipy.spatial.transform import Rotation

    executor._move_to_position_line = MagicMock(return_value=(True, '이동 완료'))

    with _patch_entry(dict(ENTRY)):
        assert executor._exec_sdc_palette_inlet_move(_job(dx=5.0, dy=-3.0, dz=10.0)) is True

    args = executor._move_to_position_line.call_args[0]
    R_m = Rotation.from_euler(
        'ZYX', [MARKER['rz'], MARKER['ry'], MARKER['rx']], degrees=True).as_matrix()
    base = np.array([MARKER['x'], MARKER['y'], MARKER['z']]) + R_m @ np.array(ENTRY['values'])
    expected = base + R_m @ np.array([5.0, -3.0, 10.0])
    assert np.allclose(np.array(args[1:4]), expected, atol=1e-6), \
        f"보정 반영 목표 {args[1:4]} ≠ 기대 {expected}"


def test_fails_without_landmark_scan(executor):
    executor.detected_landmark_pose = None
    executor._move_to_position_line = MagicMock()
    with _patch_entry(dict(ENTRY)):
        assert executor._exec_sdc_palette_inlet_move(_job()) is False
    executor._move_to_position_line.assert_not_called()
    assert 'scan_tm_landmark를 먼저 실행하세요' in _logs(executor)


def test_fails_when_entry_missing(executor):
    executor._move_to_position_line = MagicMock()
    with _patch_entry(None):
        assert executor._exec_sdc_palette_inlet_move(_job()) is False
    executor._move_to_position_line.assert_not_called()
    assert 'sdc_palette_inlet_move 항목이 없습니다' in _logs(executor)


def test_fails_on_wrong_values_count(executor):
    executor._move_to_position_line = MagicMock()
    bad = dict(ENTRY, values=[65.4, 220.74])
    with _patch_entry(bad):
        assert executor._exec_sdc_palette_inlet_move(_job()) is False
    executor._move_to_position_line.assert_not_called()
    assert '3개여야 합니다' in _logs(executor)


def test_fails_without_current_tcp(executor):
    executor.ros_node.current_tcp_pose = None
    executor._move_to_position_line = MagicMock()
    with _patch_entry(dict(ENTRY)):
        assert executor._exec_sdc_palette_inlet_move(_job()) is False
    executor._move_to_position_line.assert_not_called()
    assert '현재 TCP 위치를 알 수 없습니다' in _logs(executor)


def test_fails_when_motion_rejected(executor):
    executor._move_to_position_line = MagicMock(return_value=(False, '[안전구역] 거부'))
    with _patch_entry(dict(ENTRY)):
        assert executor._exec_sdc_palette_inlet_move(_job()) is False
    assert 'sdc_palette_inlet_move 실패' in _logs(executor)
