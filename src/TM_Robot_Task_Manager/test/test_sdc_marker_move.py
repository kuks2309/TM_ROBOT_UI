"""job_executor sdc_marker_move job(마커 frame 상대 이동·표면 평행/법선 방향·실패 조건)을 검증한다."""
import math

import numpy as np
import pytest
from unittest.mock import MagicMock
from scipy.spatial.transform import Rotation

from tm_task_manager.job_executor import JobExecutor
from tm_task_manager.recipe_manager import Job, RecipeManager

CURRENT_TCP = [-900.445, -12.905, 502.186, 90.78, -23.03, -86.66]
MARKER = {'x': -1207.308, 'y': -110.022, 'z': 740.006,
          'rx': -90.744, 'ry': -0.982, 'rz': 94.487}
R_MARKER = Rotation.from_euler(
    'ZYX', [MARKER['rz'], MARKER['ry'], MARKER['rx']], degrees=True).as_matrix()


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
    return Job(job_id=1, job_type='sdc_marker_move', params=params)


def _logs(executor):
    return "\n".join(executor.logs)


def test_job_type_is_registered():
    spec = RecipeManager.JOB_TYPES['sdc_marker_move']
    assert spec['name'] == 'sdc_marker_move'
    assert spec['category'] == 'Landmark'
    assert set(spec['params']) == {'dx', 'dy', 'dz', 'velocity', 'wait_after_command'}
    assert spec['params']['dz']['default'] == 0.0


def test_dispatch_reaches_handler(executor):
    executor._move_to_position_line = MagicMock(return_value=(True, '이동 완료'))
    assert executor._execute_job(_job(dz=10.0)) is True
    executor._move_to_position_line.assert_called_once()


def test_dz_moves_along_marker_normal_keeping_orientation(executor):
    executor._move_to_position_line = MagicMock(return_value=(True, '이동 완료'))

    assert executor._exec_sdc_marker_move(_job(dz=50.0)) is True

    args = executor._move_to_position_line.call_args[0]
    delta = np.array(args[1:4]) - np.array(CURRENT_TCP[:3])
    assert np.allclose(delta, R_MARKER[:, 2] * 50.0, atol=1e-6), \
        f"이동벡터 {delta} ≠ 마커 법선×50"
    assert np.linalg.norm(delta) == pytest.approx(50.0, abs=1e-6)
    assert args[4:7] == (CURRENT_TCP[3], CURRENT_TCP[4], CURRENT_TCP[5])
    assert 'sdc_marker_move 완료' in _logs(executor)


def test_dx_dy_move_parallel_to_marker_surface(executor):
    executor._move_to_position_line = MagicMock(return_value=(True, '이동 완료'))

    assert executor._exec_sdc_marker_move(_job(dx=10.0, dy=-20.0)) is True

    args = executor._move_to_position_line.call_args[0]
    delta = np.array(args[1:4]) - np.array(CURRENT_TCP[:3])
    normal_component = float(np.dot(delta, R_MARKER[:, 2]))
    assert abs(normal_component) < 1e-6, "표면 평행 이동에 법선 성분이 섞임"
    assert np.linalg.norm(delta) == pytest.approx(math.hypot(10.0, 20.0), abs=1e-6)


def test_fails_without_landmark_scan(executor):
    executor.detected_landmark_pose = None
    executor._move_to_position_line = MagicMock()
    assert executor._exec_sdc_marker_move(_job(dz=10.0)) is False
    executor._move_to_position_line.assert_not_called()
    assert 'scan_tm_landmark를 먼저 실행하세요' in _logs(executor)


def test_fails_without_current_tcp(executor):
    executor.ros_node.current_tcp_pose = None
    executor._move_to_position_line = MagicMock()
    assert executor._exec_sdc_marker_move(_job(dz=10.0)) is False
    executor._move_to_position_line.assert_not_called()
    assert '현재 TCP 위치를 알 수 없습니다' in _logs(executor)


def test_fails_when_motion_rejected(executor):
    executor._move_to_position_line = MagicMock(return_value=(False, '[안전구역] 거부'))
    assert executor._exec_sdc_marker_move(_job(dz=10.0)) is False
    assert 'sdc_marker_move 실패' in _logs(executor)
