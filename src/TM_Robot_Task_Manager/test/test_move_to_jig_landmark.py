import pytest
from unittest.mock import MagicMock

from tm_task_manager.job_executor import JobExecutor
from tm_task_manager.recipe_manager import Job, RecipeManager


def _landmarks():
    return {
        1: {'x': 250.0, 'y': 1000.0, 'z': -100.0, 'rx': 180.0, 'ry': 0.0, 'rz': 90.0, 'detected': True},
        2: {'x': -50.0, 'y': 1000.0, 'z': -100.0, 'rx': 180.0, 'ry': 0.0, 'rz': 90.0, 'detected': True},
        3: {'x': -50.0, 'y': 600.0, 'z': -100.0, 'rx': 180.0, 'ry': 0.0, 'rz': 90.0, 'detected': True},
        4: {'x': 250.0, 'y': 600.0, 'z': -100.0, 'rx': 180.0, 'ry': 0.0, 'rz': 90.0, 'detected': True},
    }


@pytest.fixture
def node():
    n = MagicMock()
    n.current_base_name = 'RobotBase'
    n.current_tcp_pose = [100.0, 800.0, 150.0, -180.0, 0.0, 90.0]
    return n


@pytest.fixture
def executor(node):
    ex = JobExecutor(ros_node=node)
    ex.logs = []
    ex.on_log = ex.logs.append
    ex.jig_landmark_results = _landmarks()
    ex.move_calls = []

    def _fake_move(motion_type, x, y, z, rx, ry, rz, velocity, decomposed_tcp=False):
        ex.move_calls.append((motion_type, x, y, z, rx, ry, rz, velocity, decomposed_tcp))
        return True, f"이동 완료 ({x:.2f}, {y:.2f}, {z:.2f})"

    ex._move_to_position = _fake_move
    return ex


def _job(**params):
    return Job(job_id=1, job_type='move_to_jig_landmark', params=params)


def _logs(executor):
    return "\n".join(executor.logs)


def test_moves_to_landmark_plus_offset(executor):
    assert executor._exec_move_to_jig_landmark(
        _job(jig_number=1, offset={'x': 1.5, 'y': -2.0, 'z': 120.0})) is True

    assert len(executor.move_calls) == 1
    call = executor.move_calls[0]
    assert (call[1], call[2], call[3]) == pytest.approx((251.5, 998.0, 20.0))


def test_keeps_current_tcp_orientation(executor, node):
    node.current_tcp_pose = [0.0, 0.0, 0.0, -179.0, 1.0, 88.0]
    executor._exec_move_to_jig_landmark(_job(jig_number=2, offset={'x': 0.0, 'y': 0.0, 'z': 100.0}))

    call = executor.move_calls[0]
    assert (call[4], call[5], call[6]) == pytest.approx((-179.0, 1.0, 88.0))


def test_offset_defaults_to_zero_when_missing(executor):
    executor._exec_move_to_jig_landmark(_job(jig_number=3))

    call = executor.move_calls[0]
    assert (call[1], call[2], call[3]) == pytest.approx((-50.0, 600.0, -100.0))


def test_passes_velocity_and_decomposed_tcp(executor):
    executor._exec_move_to_jig_landmark(_job(jig_number=4, velocity=15.0, decomposed_tcp=True))

    call = executor.move_calls[0]
    assert call[7] == pytest.approx(15.0)
    assert call[8] is True


def test_logs_prototype_marker(executor):
    executor._exec_move_to_jig_landmark(_job(jig_number=1))
    assert "[프로토타입]" in _logs(executor)


def test_rejects_when_scan_result_missing(executor):
    executor.jig_landmark_results = {}
    assert executor._exec_move_to_jig_landmark(_job(jig_number=1)) is False
    assert "scan_tm_landmark_jig" in _logs(executor)
    assert executor.move_calls == []


def test_rejects_when_landmark_not_detected(executor):
    executor.jig_landmark_results[1]['detected'] = False
    assert executor._exec_move_to_jig_landmark(_job(jig_number=1)) is False
    assert "미검출" in _logs(executor)
    assert executor.move_calls == []


def test_rejects_invalid_jig_number(executor):
    assert executor._exec_move_to_jig_landmark(_job(jig_number=0)) is False
    assert executor._exec_move_to_jig_landmark(_job(jig_number=5)) is False
    assert executor.move_calls == []


def test_rejects_when_base_is_not_robot_base(executor, node):
    node.current_base_name = 'vision_TM_Landmark_detection'
    assert executor._exec_move_to_jig_landmark(_job(jig_number=1)) is False
    assert "RobotBase" in _logs(executor)
    assert executor.move_calls == []


def test_rejects_when_tcp_pose_unavailable(executor, node):
    node.current_tcp_pose = []
    assert executor._exec_move_to_jig_landmark(_job(jig_number=1)) is False
    assert "TCP" in _logs(executor)
    assert executor.move_calls == []


def test_returns_false_when_motion_fails(executor):
    def _failing_move(motion_type, x, y, z, rx, ry, rz, velocity, decomposed_tcp=False):
        return False, "LINE_T 거절"

    executor._move_to_position = _failing_move
    assert executor._exec_move_to_jig_landmark(_job(jig_number=1)) is False
    assert "이동 실패" in _logs(executor)


def test_execute_job_routes_move_to_jig_landmark(executor):
    assert executor._execute_job(_job(jig_number=1)) is True
    assert len(executor.move_calls) == 1


def test_job_type_registered_as_prototype():
    spec = RecipeManager.JOB_TYPES['move_to_jig_landmark']
    assert spec['category'] == 'Landmark'
    assert spec['category'] in RecipeManager.CATEGORY_ORDER
    assert spec['prototype'] is True
    assert '프로토타입' in spec['name']
    assert spec['params']['jig_number']['min'] == 1
    assert spec['params']['jig_number']['max'] == 4
    assert spec['params']['offset']['type'] == 'dict'
    assert spec['params']['decomposed_tcp']['default'] is True


def test_other_job_types_untouched():
    assert RecipeManager.JOB_TYPES['scan_tm_landmark_jig']['params']['jig_number']['max'] == 4
    assert RecipeManager.JOB_TYPES['align_to_plane_normal']['params']['standoff_mm']['default'] == 150.0
    assert {'operator', 'save_path'} <= set(RecipeManager.JOB_TYPES['calculate_plate_pose']['params'])
    assert RecipeManager.JOB_TYPES['move_to_point']['params']['decomposed_tcp']['default'] is False
