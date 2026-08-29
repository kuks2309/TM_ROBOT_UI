"""job_executor sdc_palette_tcp_align job(마커 수직 자세식·offset 읽기·실패 조건)을 검증한다."""
import pytest
from unittest.mock import MagicMock, patch

from tm_task_manager.job_executor import JobExecutor
from tm_task_manager.recipe_manager import Job, RecipeManager
from tm_task_manager.services.config_manager import ConfigManager

CURRENT_TCP = [-845.103, -73.961, 412.213, 88.105, -20.008, -90.587]
MARKER = {'rx': -87.513, 'ry': -0.691, 'rz': 90.802}
ENTRY = {'description': 'palette 마커 수직 정렬 offset', 'type': 'tcp_orientation_offset',
         'values': [0.0, -22.0, 0.0]}


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
    return Job(job_id=1, job_type='sdc_palette_tcp_align', params=params)


def _logs(executor):
    return "\n".join(executor.logs)


def _patch_entry(entry):
    return patch.object(ConfigManager, 'get_position', return_value=entry)


def test_offset_entry_registered_in_yaml():
    entry = ConfigManager().get_position('sdc_palette_tcp_align')
    assert entry is not None
    assert entry['type'] == 'tcp_orientation_offset'
    assert entry['values'] == [0.0, -22.0, 0.0]


def test_job_type_is_registered():
    spec = RecipeManager.JOB_TYPES['sdc_palette_tcp_align']
    assert spec['name'] == 'sdc_palette_tcp_align'
    assert spec['category'] == 'Landmark'
    assert set(spec['params']) == {'velocity', 'wait_after_command'}
    assert spec['params']['velocity']['default'] == 10.0


def test_dispatch_reaches_handler(executor):
    executor._move_to_position_line = MagicMock(return_value=(True, '이동 완료'))
    with _patch_entry(dict(ENTRY)):
        assert executor._execute_job(_job()) is True
    executor._move_to_position_line.assert_called_once()


def test_applies_sign_flip_and_ry_offset(executor):
    executor._move_to_position_line = MagicMock(return_value=(True, '이동 완료'))

    with _patch_entry(dict(ENTRY)):
        assert executor._exec_sdc_palette_tcp_align(_job()) is True

    executor._move_to_position_line.assert_called_once_with(
        'tcp', CURRENT_TCP[0], CURRENT_TCP[1], CURRENT_TCP[2],
        pytest.approx(87.513), pytest.approx(-22.691), pytest.approx(-90.802), 10.0)
    assert 'sdc_palette_tcp_align 완료' in _logs(executor)


def test_fails_without_landmark_scan(executor):
    executor.detected_landmark_pose = None
    executor._move_to_position_line = MagicMock()
    with _patch_entry(dict(ENTRY)):
        assert executor._exec_sdc_palette_tcp_align(_job()) is False
    executor._move_to_position_line.assert_not_called()
    assert 'scan_tm_landmark를 먼저 실행하세요' in _logs(executor)


def test_fails_when_entry_missing(executor):
    executor._move_to_position_line = MagicMock()
    with _patch_entry(None):
        assert executor._exec_sdc_palette_tcp_align(_job()) is False
    executor._move_to_position_line.assert_not_called()
    assert 'sdc_palette_tcp_align 항목이 없습니다' in _logs(executor)


def test_fails_on_wrong_values_count(executor):
    executor._move_to_position_line = MagicMock()
    bad = dict(ENTRY, values=[0.0, -22.0])
    with _patch_entry(bad):
        assert executor._exec_sdc_palette_tcp_align(_job()) is False
    executor._move_to_position_line.assert_not_called()
    assert '3개여야 합니다' in _logs(executor)


def test_fails_without_current_tcp(executor):
    executor.ros_node.current_tcp_pose = None
    executor._move_to_position_line = MagicMock()
    with _patch_entry(dict(ENTRY)):
        assert executor._exec_sdc_palette_tcp_align(_job()) is False
    executor._move_to_position_line.assert_not_called()
    assert '현재 TCP 위치를 알 수 없습니다' in _logs(executor)


def test_fails_when_motion_rejected(executor):
    executor._move_to_position_line = MagicMock(return_value=(False, '[안전구역] 거부'))
    with _patch_entry(dict(ENTRY)):
        assert executor._exec_sdc_palette_tcp_align(_job()) is False
    assert 'sdc_palette_tcp_align 실패' in _logs(executor)
