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
INLET_TAUGHT = (-886.82, -14.21, 523.57)
YAML_OFFSET = [62.55, 220.88, -310.18]


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


def _patch_entry(entry):
    return patch.object(ConfigManager, 'get_position', return_value=entry)


def test_offset_entry_registered_in_yaml():
    entry = ConfigManager().get_position('sdc_palette_inlet_move')
    assert entry is not None
    assert entry['type'] == 'marker_frame_offset'
    assert entry['values'] == YAML_OFFSET


def test_job_type_is_registered():
    spec = RecipeManager.JOB_TYPES['sdc_palette_inlet_move']
    assert spec['name'] == 'sdc_palette_inlet_move'
    assert spec['category'] == 'Landmark'
    assert set(spec['params']) == {'velocity', 'wait_after_command'}
    assert spec['params']['velocity']['default'] == 10.0


def test_dispatch_reaches_handler(executor):
    executor._move_to_position_line = MagicMock(return_value=(True, '이동 완료'))
    with _patch_entry(dict(ENTRY)):
        assert executor._execute_job(_job()) is True
    executor._move_to_position_line.assert_called_once()


def test_moves_to_marker_relative_inlet_keeping_orientation(executor):
    executor._move_to_position_line = MagicMock(return_value=(True, '이동 완료'))

    with _patch_entry(dict(ENTRY)):
        assert executor._exec_sdc_palette_inlet_move(_job()) is True

    args = executor._move_to_position_line.call_args[0]
    assert args[0] == 'tcp'
    assert args[1] == pytest.approx(INLET_TAUGHT[0], abs=0.1)
    assert args[2] == pytest.approx(INLET_TAUGHT[1], abs=0.1)
    assert args[3] == pytest.approx(INLET_TAUGHT[2], abs=0.1)
    assert args[4:7] == (CURRENT_TCP[3], CURRENT_TCP[4], CURRENT_TCP[5])
    assert args[7] == 10.0
    assert 'sdc_palette_inlet_move 완료' in _logs(executor)


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
