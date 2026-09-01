"""job_executor 평면 정렬/측정 job 을 검증한다."""
import math
import pytest
from unittest.mock import MagicMock

from tm_task_manager.job_executor import (
    JobExecutor,
    PLANE_ALIGN_MAX_DIAGONAL_DIFF_MM,
    PLANE_ALIGN_MAX_TILT_DEG,
)
from tm_task_manager.recipe_manager import Job


def _angle_difference_deg(target, current):
    diff = (target - current + 180.0) % 360.0 - 180.0
    return abs(diff)


def _rectangle_landmarks(diagonal_skew_mm=0.0):
    return {
        1: {'x': 0.0,                     'y': 0.0,   'z': 0.0, 'rx': 0.0, 'ry': 0.0, 'rz': 0.0},
        2: {'x': 0.0,                     'y': 100.0, 'z': 0.0, 'rx': 0.0, 'ry': 0.0, 'rz': 0.0},
        3: {'x': 200.0,                   'y': 0.0,   'z': 0.0, 'rx': 0.0, 'ry': 0.0, 'rz': 0.0},
        4: {'x': 200.0 + diagonal_skew_mm, 'y': 100.0, 'z': 0.0, 'rx': 0.0, 'ry': 0.0, 'rz': 0.0},
    }


HORIZONTAL_PLANE = {'x': 100.0, 'y': 50.0, 'z': 0.0, 'rx': 0.0, 'ry': 0.0, 'rz': 0.0}
TILTED_PLANE = {'x': 100.0, 'y': 50.0, 'z': 0.0, 'rx': 0.0, 'ry': 10.0, 'rz': 0.0}
FLIPPED_PLANE = {'x': 100.0, 'y': 50.0, 'z': 0.0, 'rx': 180.0, 'ry': 0.0, 'rz': 0.0}


@pytest.fixture
def node():
    n = MagicMock()
    n.current_base_name = 'RobotBase'
    n.current_tcp_pose = [100.0, 50.0, 400.0, 180.0, 0.0, 0.0]
    n.motion_service._angle_difference_deg = _angle_difference_deg
    return n


@pytest.fixture
def executor(node):
    ex = JobExecutor(ros_node=node)
    ex.logs = []
    ex.on_log = ex.logs.append
    ex.jig_landmark_results = _rectangle_landmarks()
    ex.line_calls = []

    def _fake_line(motion_type, x, y, z, rx, ry, rz, velocity):
        ex.line_calls.append((motion_type, x, y, z, rx, ry, rz, velocity))
        return True, f"이동 완료 ({x:.2f}, {y:.2f}, {z:.2f})"

    ex._move_to_position_line = _fake_line
    return ex


def _align_job(**params):
    return Job(job_id=1, job_type='align_to_plane_normal', params=params)


def _measure_job():
    return Job(job_id=2, job_type='measure_plane_distance', params={})


def _logs(executor):
    return "\n".join(executor.logs)


def test_rejects_when_plate_pose_missing(executor):
    executor.detected_plate_pose = None
    assert executor._exec_align_to_plane_normal(_align_job()) is False
    assert "calculate_plate_pose" in _logs(executor)
    assert executor.line_calls == []


def test_rejects_when_base_is_not_robot_base(executor, node):
    node.current_base_name = 'vision_TM_Landmark_detection'
    executor.detected_plate_pose = dict(HORIZONTAL_PLANE)
    assert executor._exec_align_to_plane_normal(_align_job()) is False
    assert "RobotBase" in _logs(executor)
    assert executor.line_calls == []


def test_rejects_non_positive_standoff(executor):
    executor.detected_plate_pose = dict(HORIZONTAL_PLANE)
    assert executor._exec_align_to_plane_normal(_align_job(standoff_mm=0.0)) is False
    assert executor._exec_align_to_plane_normal(_align_job(standoff_mm=-5.0)) is False
    assert "standoff_mm" in _logs(executor)
    assert executor.line_calls == []


def test_rejects_when_landmark_layout_is_skewed(executor):
    executor.detected_plate_pose = dict(HORIZONTAL_PLANE)
    executor.jig_landmark_results = _rectangle_landmarks(diagonal_skew_mm=80.0)
    assert executor._exec_align_to_plane_normal(_align_job()) is False
    assert "대각선" in _logs(executor)
    assert executor.line_calls == []


def test_rejects_when_landmark_results_incomplete(executor):
    executor.detected_plate_pose = dict(HORIZONTAL_PLANE)
    executor.jig_landmark_results = {1: _rectangle_landmarks()[1]}
    assert executor._exec_align_to_plane_normal(_align_job()) is False
    assert "scan_tm_landmark_jig" in _logs(executor)
    assert executor.line_calls == []


def test_rejects_flipped_normal_via_tilt_guard(executor):
    executor.detected_plate_pose = dict(FLIPPED_PLANE)
    assert executor._exec_align_to_plane_normal(_align_job()) is False
    logs = _logs(executor)
    assert "기울기" in logs and "뒤집" in logs
    assert executor.line_calls == []


def test_rejects_tilt_above_limit(executor):
    executor.detected_plate_pose = {'x': 0.0, 'y': 0.0, 'z': 0.0,
                                    'rx': 0.0, 'ry': 45.0, 'rz': 0.0}
    assert executor._exec_align_to_plane_normal(
        _align_job(max_tilt_deg=PLANE_ALIGN_MAX_TILT_DEG)) is False
    assert executor.line_calls == []


def test_rejects_when_tcp_pose_unavailable(executor, node):
    node.current_tcp_pose = []
    executor.detected_plate_pose = dict(HORIZONTAL_PLANE)
    assert executor._exec_align_to_plane_normal(_align_job()) is False
    assert "TCP" in _logs(executor)
    assert executor.line_calls == []


def test_two_stage_motion_rotates_then_approaches(executor):
    executor.detected_plate_pose = dict(TILTED_PLANE)
    assert executor._exec_align_to_plane_normal(_align_job(standoff_mm=150.0)) is True

    assert len(executor.line_calls) >= 2

    first = executor.line_calls[0]
    assert (first[1], first[2], first[3]) == pytest.approx((100.0, 50.0, 400.0))

    target_orientation = (first[4], first[5], first[6])
    for call in executor.line_calls[1:]:
        assert (call[4], call[5], call[6]) == pytest.approx(target_orientation)


def test_final_position_is_center_plus_normal_standoff(executor):
    executor.detected_plate_pose = dict(TILTED_PLANE)
    executor._exec_align_to_plane_normal(_align_job(standoff_mm=150.0))

    normal_x = math.sin(math.radians(10.0)) * 150.0
    normal_z = math.cos(math.radians(10.0)) * 150.0
    last = executor.line_calls[-1]
    assert (last[1], last[2], last[3]) == pytest.approx(
        (100.0 + normal_x, 50.0, 0.0 + normal_z)
    )


def test_descent_uses_xy_before_z(executor):
    executor.detected_plate_pose = dict(TILTED_PLANE)
    executor._exec_align_to_plane_normal(_align_job(standoff_mm=150.0))

    approach = executor.line_calls[1:]
    assert len(approach) == 2
    assert approach[0][3] == pytest.approx(400.0)
    assert approach[1][3] < approach[0][3]


def test_skips_rotation_when_already_aligned(executor):
    executor.detected_plate_pose = dict(HORIZONTAL_PLANE)
    assert executor._exec_align_to_plane_normal(_align_job(standoff_mm=150.0)) is True
    assert "자세 정렬 생략" in _logs(executor)
    for call in executor.line_calls:
        assert (call[1], call[2], call[3]) != pytest.approx((100.0, 50.0, 400.0))


def test_aborts_without_ptp_fallback_on_failure(executor):
    executor.detected_plate_pose = dict(TILTED_PLANE)

    def _failing_line(motion_type, x, y, z, rx, ry, rz, velocity):
        executor.line_calls.append((motion_type, x, y, z, rx, ry, rz, velocity))
        return False, "LINE_T 거절"

    executor._move_to_position_line = _failing_line
    assert executor._exec_align_to_plane_normal(_align_job()) is False
    assert len(executor.line_calls) == 1
    assert "중단" in _logs(executor)


def test_rz_mode_plane_is_accepted(executor):
    executor.detected_plate_pose = dict(TILTED_PLANE)
    assert executor._exec_align_to_plane_normal(
        _align_job(rz_mode='plane', standoff_mm=150.0)) is True
    assert executor.line_calls


def test_rejects_unknown_rz_mode(executor):
    executor.detected_plate_pose = dict(TILTED_PLANE)
    assert executor._exec_align_to_plane_normal(_align_job(rz_mode='auto')) is False
    assert "목표 자세 계산 실패" in _logs(executor)
    assert executor.line_calls == []


def test_measure_returns_positive_above_plane(executor):
    executor.detected_plate_pose = dict(HORIZONTAL_PLANE)
    assert executor._exec_measure_plane_distance(_measure_job()) is True
    assert executor.measured_plane_distance == pytest.approx(400.0)
    assert "+400.000mm" in _logs(executor)


def test_measure_reports_zero_alignment_when_perpendicular(executor):
    executor.detected_plate_pose = dict(HORIZONTAL_PLANE)
    executor._exec_measure_plane_distance(_measure_job())
    assert "수직 정렬 편차: 0.000°" in _logs(executor)


def test_measure_reports_alignment_error_when_tilted(executor, node):
    node.current_tcp_pose = [100.0, 50.0, 400.0, 180.0, 10.0, 0.0]
    executor.detected_plate_pose = dict(HORIZONTAL_PLANE)
    executor._exec_measure_plane_distance(_measure_job())
    assert "수직 정렬 편차: 10.000°" in _logs(executor)


def test_measure_warns_on_negative_distance(executor):
    executor.detected_plate_pose = dict(FLIPPED_PLANE)
    assert executor._exec_measure_plane_distance(_measure_job()) is True
    assert executor.measured_plane_distance == pytest.approx(-400.0)
    assert "거리가 음수" in _logs(executor)


def test_measure_does_not_move_robot(executor):
    executor.detected_plate_pose = dict(HORIZONTAL_PLANE)
    executor._exec_measure_plane_distance(_measure_job())
    assert executor.line_calls == []


def test_measure_rejects_without_plate_pose(executor):
    executor.detected_plate_pose = None
    assert executor._exec_measure_plane_distance(_measure_job()) is False
    assert executor.measured_plane_distance is None


def test_measure_rejects_without_tcp_pose(executor, node):
    node.current_tcp_pose = []
    executor.detected_plate_pose = dict(HORIZONTAL_PLANE)
    assert executor._exec_measure_plane_distance(_measure_job()) is False


def test_execute_job_routes_align(executor):
    executor.detected_plate_pose = dict(HORIZONTAL_PLANE)
    assert executor._execute_job(_align_job(standoff_mm=150.0)) is True


def test_execute_job_routes_measure(executor):
    executor.detected_plate_pose = dict(HORIZONTAL_PLANE)
    assert executor._execute_job(_measure_job()) is True
    assert executor.measured_plane_distance is not None


def _final_target(executor):
    _, x, y, z, rx, ry, rz, _ = executor.line_calls[-1]
    return x, y, z, rx, ry, rz


def test_zero_offset_target_matches_plane_center(executor):
    executor.detected_plate_pose = dict(HORIZONTAL_PLANE)
    assert executor._exec_align_to_plane_normal(_align_job(standoff_mm=150.0)) is True

    x, y, z, _, _, _ = _final_target(executor)
    assert (x, y, z) == pytest.approx((100.0, 50.0, 150.0))


def test_tool_offset_shifts_target_in_tool_frame(executor):
    executor.detected_plate_pose = dict(HORIZONTAL_PLANE)
    assert executor._exec_align_to_plane_normal(
        _align_job(standoff_mm=150.0, offset_x=10.0, offset_y=4.0)) is True

    x, y, z, _, _, _ = _final_target(executor)
    assert x == pytest.approx(110.0, abs=1e-6)
    assert y == pytest.approx(46.0, abs=1e-6)
    assert z == pytest.approx(150.0, abs=1e-6)
    assert "그리퍼 오차 적용" in _logs(executor)


def test_tool_offset_rz_rotates_target(executor):
    executor.detected_plate_pose = dict(HORIZONTAL_PLANE)
    executor._exec_align_to_plane_normal(_align_job(standoff_mm=150.0))
    base_rz = _final_target(executor)[5]

    executor.line_calls = []
    executor._exec_align_to_plane_normal(_align_job(standoff_mm=150.0, offset_rz=90.0))
    shifted_rz = _final_target(executor)[5]

    assert _angle_difference_deg(shifted_rz, base_rz) == pytest.approx(90.0, abs=1e-6)


def test_tool_offset_does_not_move_along_normal(executor):
    executor.detected_plate_pose = dict(HORIZONTAL_PLANE)
    assert executor._exec_align_to_plane_normal(
        _align_job(standoff_mm=150.0, offset_x=25.0, offset_y=-15.0)) is True

    assert _final_target(executor)[2] == pytest.approx(150.0, abs=1e-6)


def test_estimate_offset_returns_zero_when_already_on_target(executor, node):
    executor.detected_plate_pose = dict(HORIZONTAL_PLANE)
    node.current_tcp_pose = [100.0, 50.0, 150.0, 180.0, 0.0, 0.0]

    offset, message = executor.estimate_plane_align_tool_offset(
        {'standoff_mm': 150.0, 'rz_mode': 'plane'})

    assert offset is not None
    for key in ('x', 'y', 'rx', 'ry'):
        assert offset[key] == pytest.approx(0.0, abs=1e-6)
    assert "그리퍼 오차 추산" in message


def test_estimate_offset_recovers_manual_correction(executor, node):
    executor.detected_plate_pose = dict(HORIZONTAL_PLANE)
    node.current_tcp_pose = [112.0, 47.0, 150.0, 180.0, 0.0, 30.0]

    offset, _ = executor.estimate_plane_align_tool_offset(
        {'standoff_mm': 150.0, 'rz_mode': 'plane'})

    node.current_tcp_pose = [0.0, 0.0, 500.0, 180.0, 0.0, 0.0]

    params = {'standoff_mm': 150.0, 'rz_mode': 'plane'}
    params.update({f'offset_{k}': v for k, v in offset.items()})
    assert executor._exec_align_to_plane_normal(_align_job(**params)) is True

    x, y, z, rx, ry, rz = _final_target(executor)
    assert (x, y, z) == pytest.approx((112.0, 47.0, 150.0), abs=1e-6)
    assert _angle_difference_deg(rz, 30.0) == pytest.approx(0.0, abs=1e-6)


def test_estimate_offset_ignores_existing_offset_params(executor, node):
    executor.detected_plate_pose = dict(HORIZONTAL_PLANE)
    node.current_tcp_pose = [110.0, 50.0, 150.0, 180.0, 0.0, 0.0]

    first, _ = executor.estimate_plane_align_tool_offset(
        {'standoff_mm': 150.0, 'rz_mode': 'plane'})
    second, _ = executor.estimate_plane_align_tool_offset(
        {'standoff_mm': 150.0, 'rz_mode': 'plane', 'offset_x': first['x']})

    assert second['x'] == pytest.approx(first['x'], abs=1e-9)


def test_estimate_offset_reports_ignored_z_gap(executor, node):
    executor.detected_plate_pose = dict(HORIZONTAL_PLANE)
    node.current_tcp_pose = [100.0, 50.0, 170.0, 180.0, 0.0, 0.0]

    offset, message = executor.estimate_plane_align_tool_offset(
        {'standoff_mm': 150.0, 'rz_mode': 'plane'})

    assert offset is not None
    assert "standoff_mm" in message


def test_estimate_offset_fails_without_plate_pose(executor):
    executor.detected_plate_pose = None
    offset, message = executor.estimate_plane_align_tool_offset({'standoff_mm': 150.0})

    assert offset is None
    assert "실패" in message


def test_job_types_registered_with_expected_params():
    from tm_task_manager.recipe_manager import RecipeManager

    align = RecipeManager.JOB_TYPES['align_to_plane_normal']
    assert align['category'] == 'Landmark'
    assert align['params']['standoff_mm']['default'] == 150.0
    assert align['params']['rz_mode']['default'] == 'keep'
    assert align['params']['rz_mode']['choices'] == ['keep', 'plane']
    assert align['params']['velocity']['default'] == 10.0
    assert align['params']['max_tilt_deg']['default'] == PLANE_ALIGN_MAX_TILT_DEG
    assert align['params']['max_diagonal_diff_mm']['default'] == PLANE_ALIGN_MAX_DIAGONAL_DIFF_MM

    for axis in ('x', 'y', 'rx', 'ry', 'rz'):
        assert align['params'][f'offset_{axis}']['default'] == 0.0
    assert 'offset_z' not in align['params']

    measure = RecipeManager.JOB_TYPES['measure_plane_distance']
    assert measure['category'] == 'Landmark'
    assert measure['params'] == {}
