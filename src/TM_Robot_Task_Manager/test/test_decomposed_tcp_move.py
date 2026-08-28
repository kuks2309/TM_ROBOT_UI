import math
import pytest
from unittest.mock import MagicMock

from tm_task_manager.job_executor import (
    JobExecutor,
    DECOMPOSED_MIN_STEP_MM,
    DECOMPOSED_MIN_STEP_DEG,
)
from tm_task_manager.recipe_manager import Job, RecipeManager


TCP = [100.0, 200.0, 300.0, 0.0, 90.0, 0.0]

REAL_LOW = [-268.2805480957031, 188.4594268798828, 247.41114807128906,
            -179.99981689453125, -0.00025467135128565127, 179.9998779296875]

REAL_HIGH = [-238.2801208496094, 198.46096801757812, 297.4110107421875,
             179.99942016601562, -0.00031232833280228078, 179.99989318847656]

EQUIVALENT_ANGLE_PAIRS = [
    (180.0, -180.0),
    (-180.0, 180.0),
    (180.0, -179.99981689453125),
    (-180.0, 179.99942016601562),
    (0.0, -0.0),
    (0.0, 360.0),
    (-180.0, 540.0),
]


@pytest.fixture
def node():
    n = MagicMock()
    n.current_base_name = 'RobotBase'
    n.current_tcp_pose = list(TCP)
    n._call_set_positions = MagicMock(return_value=(True, "이동 완료"))
    return n


@pytest.fixture
def executor(node):
    ex = JobExecutor(ros_node=node)
    ex.logs = []
    ex.on_log = ex.logs.append
    return ex


def make_job(job_type='move_to_point', **params):
    return Job(job_id=1, job_type=job_type, params=params)


def sent_positions(node):
    return [call.args[1] for call in node._call_set_positions.call_args_list]


def sent_motion_types(node):
    return [call.args[0] for call in node._call_set_positions.call_args_list]


def labels(waypoints):
    return [label for label, _ in waypoints]


class TestBuildDecomposedWaypoints:
    def build(self, executor, target, current=None):
        return executor._build_decomposed_tcp_waypoints(current or list(TCP), target)

    def test_ascend_rotation_then_z_then_long_axis(self, executor):
        waypoints, order = self.build(executor, [150.0, 210.0, 400.0, 10.0, 90.0, 0.0])

        assert order == '상승/수평'
        assert waypoints == [
            ('회전', [100.0, 200.0, 300.0, 10.0, 90.0, 0.0]),
            ('Z축', [100.0, 200.0, 400.0, 10.0, 90.0, 0.0]),
            ('X축', [150.0, 200.0, 400.0, 10.0, 90.0, 0.0]),
            ('Y축', [150.0, 210.0, 400.0, 10.0, 90.0, 0.0]),
        ]

    def test_descend_reverses_translation_order_z_last(self, executor):
        waypoints, order = self.build(executor, [150.0, 210.0, 250.0, 10.0, 90.0, 0.0])

        assert order == '하강'
        assert waypoints == [
            ('회전', [100.0, 200.0, 300.0, 10.0, 90.0, 0.0]),
            ('X축', [150.0, 200.0, 300.0, 10.0, 90.0, 0.0]),
            ('Y축', [150.0, 210.0, 300.0, 10.0, 90.0, 0.0]),
            ('Z축', [150.0, 210.0, 250.0, 10.0, 90.0, 0.0]),
        ]

    def test_rotation_is_first_in_both_directions(self, executor):
        up, _ = self.build(executor, [150.0, 210.0, 400.0, 10.0, 90.0, 0.0])
        down, _ = self.build(executor, [150.0, 210.0, 250.0, 10.0, 90.0, 0.0])

        assert up[0][0] == '회전'
        assert down[0][0] == '회전'

    def test_longer_y_axis_goes_before_x(self, executor):
        waypoints, _ = self.build(executor, [110.0, 260.0, 400.0, 0.0, 90.0, 0.0])

        assert labels(waypoints) == ['Z축', 'Y축', 'X축']

    def test_equal_xy_delta_prefers_x_first(self, executor):
        waypoints, _ = self.build(executor, [150.0, 250.0, 400.0, 0.0, 90.0, 0.0])

        assert labels(waypoints) == ['Z축', 'X축', 'Y축']

    def test_no_rotation_step_when_orientation_unchanged(self, executor):
        waypoints, _ = self.build(executor, [150.0, 210.0, 400.0, 0.0, 90.0, 0.0])

        assert labels(waypoints) == ['Z축', 'X축', 'Y축']

    def test_same_height_keeps_ascend_order_without_z_step(self, executor):
        waypoints, order = self.build(executor, [150.0, 210.0, 300.0, 0.0, 90.0, 0.0])

        assert order == '상승/수평'
        assert labels(waypoints) == ['X축', 'Y축']

    def test_pure_z_move_is_single_step(self, executor):
        waypoints, _ = self.build(executor, [100.0, 200.0, 400.0, 0.0, 90.0, 0.0])

        assert labels(waypoints) == ['Z축']

    def test_no_waypoints_when_already_at_target(self, executor):
        waypoints, _ = self.build(executor, list(TCP))

        assert waypoints == []

    def test_sub_threshold_deltas_produce_no_step(self, executor):
        tiny = DECOMPOSED_MIN_STEP_MM / 10.0
        target = [TCP[0] + tiny, TCP[1] + tiny, TCP[2] + tiny, 0.0, 90.0, 0.0]

        waypoints, _ = self.build(executor, target)

        assert waypoints == []

    def test_sub_threshold_axis_is_folded_into_next_step(self, executor):
        tiny = DECOMPOSED_MIN_STEP_MM / 10.0
        target = [TCP[0] + tiny, 260.0, 400.0, 0.0, 90.0, 0.0]

        waypoints, _ = self.build(executor, target)

        assert labels(waypoints) == ['Z축', 'Y축']
        assert waypoints[-1][1][:3] == pytest.approx(target[:3])

    def test_final_waypoint_equals_exact_target(self, executor):
        target = [150.0, 210.0, 250.0, 10.0, 85.0, 5.0]

        waypoints, _ = self.build(executor, target)

        assert waypoints[-1][1] == pytest.approx(target)

    def test_rotation_only_move_keeps_position(self, executor):
        waypoints, _ = self.build(executor, [100.0, 200.0, 300.0, 15.0, 90.0, 0.0])

        assert labels(waypoints) == ['회전']
        assert waypoints[0][1][:3] == pytest.approx(TCP[:3])

    @pytest.mark.parametrize('axis', [3, 4, 5])
    @pytest.mark.parametrize('target_angle,current_angle', EQUIVALENT_ANGLE_PAIRS)
    def test_equivalent_angles_emit_no_rotation_step(self, executor, axis,
                                                     target_angle, current_angle):
        current = [100.0, 200.0, 300.0, 0.0, 0.0, 0.0]
        current[axis] = current_angle
        target = [100.0, 200.0, 400.0, 0.0, 0.0, 0.0]
        target[axis] = target_angle

        waypoints, _ = self.build(executor, target, current=current)

        assert labels(waypoints) == ['Z축']

    @pytest.mark.parametrize('axis', [3, 4, 5])
    @pytest.mark.parametrize('current_angle,target_angle', [
        (180.0, 170.0),
        (-180.0, 170.0),
        (179.9994, -170.0),
        (170.0, -170.0),
        (-179.9998, 179.0),
    ])
    def test_real_rotation_near_wrap_is_still_detected(self, executor, axis,
                                                       current_angle, target_angle):
        current = [100.0, 200.0, 300.0, 0.0, 0.0, 0.0]
        current[axis] = current_angle
        target = [100.0, 200.0, 400.0, 0.0, 0.0, 0.0]
        target[axis] = target_angle

        waypoints, _ = self.build(executor, target, current=current)

        assert labels(waypoints) == ['회전', 'Z축']

    def test_rotation_threshold_uses_shortest_arc(self, executor):
        current = [100.0, 200.0, 300.0, 179.95, 0.0, 0.0]
        target = [100.0, 200.0, 400.0, -179.99, 0.0, 0.0]

        waypoints, _ = self.build(executor, target, current=current)

        assert labels(waypoints) == ['Z축']

    def test_rotation_threshold_respected(self, executor):
        tiny = DECOMPOSED_MIN_STEP_DEG / 10.0
        waypoints, _ = self.build(executor, [100.0, 200.0, 400.0, tiny, 90.0, 0.0])

        assert labels(waypoints) == ['Z축']


class TestDecomposedExecution:
    def test_option_off_sends_single_diagonal_command(self, executor, node):
        job = make_job(X=150.0, Y=210.0, Z=400.0, Rx=0.0, Ry=90.0, Rz=0.0, velocity=25.0)

        assert executor._exec_move_to_point(job) is True
        assert node._call_set_positions.call_count == 1

    def test_option_on_splits_into_sequential_commands(self, executor, node):
        job = make_job(X=150.0, Y=210.0, Z=400.0, Rx=0.0, Ry=90.0, Rz=0.0,
                       velocity=25.0, decomposed_tcp=True)

        assert executor._exec_move_to_point(job) is True

        positions = sent_positions(node)
        assert len(positions) == 3
        assert positions[0][:3] == pytest.approx([0.100, 0.200, 0.400])
        assert positions[1][:3] == pytest.approx([0.150, 0.200, 0.400])
        assert positions[2][:3] == pytest.approx([0.150, 0.210, 0.400])

    def test_every_step_uses_line_t_for_straight_path(self, executor, node):
        from tm_msgs.srv import SetPositions

        job = make_job(X=150.0, Y=210.0, Z=400.0, Rx=10.0, Ry=90.0, Rz=0.0,
                       velocity=25.0, decomposed_tcp=True)

        assert executor._exec_move_to_point(job) is True

        types = sent_motion_types(node)
        assert len(types) == 4
        for motion_type in types:
            assert motion_type is SetPositions.Request.LINE_T
            assert motion_type is not SetPositions.Request.PTP_T

    def test_option_off_still_uses_ptp(self, executor, node):
        from tm_msgs.srv import SetPositions

        job = make_job(X=150.0, Y=210.0, Z=400.0, Rx=0.0, Ry=90.0, Rz=0.0, velocity=25.0)

        assert executor._exec_move_to_point(job) is True
        assert sent_motion_types(node) == [SetPositions.Request.PTP_T]

    def test_every_step_moves_only_one_translation_axis(self, executor, node):
        job = make_job(X=150.0, Y=210.0, Z=400.0, Rx=0.0, Ry=90.0, Rz=0.0,
                       velocity=25.0, decomposed_tcp=True)

        executor._exec_move_to_point(job)

        previous = [v / 1000.0 for v in TCP[:3]]
        for position in sent_positions(node):
            moved = [i for i in range(3)
                     if abs(position[i] - previous[i]) >= DECOMPOSED_MIN_STEP_MM / 1000.0]
            assert len(moved) == 1
            previous = list(position[:3])

    def test_descending_move_lowers_z_last(self, executor, node):
        job = make_job(X=150.0, Y=210.0, Z=250.0, Rx=0.0, Ry=90.0, Rz=0.0,
                       velocity=25.0, decomposed_tcp=True)

        assert executor._exec_move_to_point(job) is True

        positions = sent_positions(node)
        assert len(positions) == 3
        assert positions[0][2] == pytest.approx(0.300)
        assert positions[1][2] == pytest.approx(0.300)
        assert positions[2][:3] == pytest.approx([0.150, 0.210, 0.250])

    def test_rotation_applied_on_first_command(self, executor, node):
        job = make_job(X=150.0, Y=210.0, Z=400.0, Rx=10.0, Ry=90.0, Rz=0.0,
                       velocity=25.0, decomposed_tcp=True)

        assert executor._exec_move_to_point(job) is True

        positions = sent_positions(node)
        assert len(positions) == 4
        assert positions[0][:3] == pytest.approx([0.100, 0.200, 0.300])
        for position in positions:
            assert position[3] == pytest.approx(math.radians(10.0))

    def test_velocity_forwarded_to_every_step(self, executor, node):
        job = make_job(X=150.0, Y=210.0, Z=400.0, Rx=0.0, Ry=90.0, Rz=0.0,
                       velocity=33.0, decomposed_tcp=True)

        executor._exec_move_to_point(job)

        for call in node._call_set_positions.call_args_list:
            assert call.kwargs['velocity'] == 33.0

    def test_aborts_remaining_steps_on_failure(self, executor, node):
        node._call_set_positions = MagicMock(return_value=(False, "PTP 거절"))
        job = make_job(X=150.0, Y=210.0, Z=400.0, Rx=0.0, Ry=90.0, Rz=0.0,
                       velocity=25.0, decomposed_tcp=True)

        assert executor._exec_move_to_point(job) is False
        assert node._call_set_positions.call_count == 1

    def test_stop_request_halts_before_next_step(self, executor, node):
        job = make_job(X=150.0, Y=210.0, Z=400.0, Rx=0.0, Ry=90.0, Rz=0.0,
                       velocity=25.0, decomposed_tcp=True)
        executor._stop_requested = True

        assert executor._exec_move_to_point(job) is False
        assert node._call_set_positions.call_count == 0

    def test_no_command_when_already_at_target(self, executor, node):
        job = make_job(X=100.0, Y=200.0, Z=300.0, Rx=0.0, Ry=90.0, Rz=0.0,
                       velocity=25.0, decomposed_tcp=True)

        assert executor._exec_move_to_point(job) is True
        assert node._call_set_positions.call_count == 0

    def test_fails_when_tcp_pose_unavailable(self, executor, node):
        node.current_tcp_pose = None
        job = make_job(X=150.0, Y=210.0, Z=400.0, Rx=0.0, Ry=90.0, Rz=0.0,
                       velocity=25.0, decomposed_tcp=True)

        assert executor._exec_move_to_point(job) is False
        assert node._call_set_positions.call_count == 0

    def test_joint_mode_falls_back_to_single_ptp_j(self, executor, node):
        job = make_job(motion_type='joint', X=10.0, Y=20.0, Z=30.0,
                       Rx=0.0, Ry=0.0, Rz=0.0, velocity=25.0, decomposed_tcp=True)

        assert executor._exec_move_to_point(job) is True
        assert node._call_set_positions.call_count == 1
        assert any('joint 모드는 축 분해 불가' in log for log in executor.logs)

    def test_go_home_supports_the_option(self, executor, node):
        job = make_job(job_type='go_home', X=150.0, Y=210.0, Z=400.0,
                       Rx=0.0, Ry=90.0, Rz=0.0, velocity=20.0, decomposed_tcp=True)

        assert executor._exec_go_home(job) is True
        assert node._call_set_positions.call_count == 3

    def test_dispatch_via_execute_job(self, executor, node):
        job = make_job(X=150.0, Y=210.0, Z=400.0, Rx=0.0, Ry=90.0, Rz=0.0,
                       velocity=25.0, decomposed_tcp=True)

        assert executor._execute_job(job) is True
        assert node._call_set_positions.call_count == 3


class TestRealRobotScenarios:
    """2026-08-10 실기(169.254.122.16, 10%) 에서 관측된 케이스를 실측 좌표로 고정한다.

    로봇이 보고하는 자세는 ±180 경계에서 -179.9998 ↔ 179.9994 로 오가므로,
    정규화 없는 각도 비교는 여기서 359.99° 로 오판해 무의미한 회전 단계를 만든다.
    아래 기대값은 실기 로그에서 그대로 옮긴 것이다.
    """

    def build(self, executor, current, target):
        return executor._build_decomposed_tcp_waypoints(list(current), list(target))

    def test_descend_from_high_to_low_matches_field_log(self, executor):
        target = [REAL_LOW[0], REAL_LOW[1], REAL_LOW[2], 180.0, 0.0, 180.0]

        waypoints, order = self.build(executor, REAL_HIGH, target)

        assert order == '하강'
        assert labels(waypoints) == ['X축', 'Y축', 'Z축']

    def test_ascend_from_low_to_high_matches_field_log(self, executor):
        target = [REAL_HIGH[0], REAL_HIGH[1], REAL_HIGH[2], 180.0, 0.0, 180.0]

        waypoints, order = self.build(executor, REAL_LOW, target)

        assert order == '상승/수평'
        assert labels(waypoints) == ['Z축', 'X축', 'Y축']

    def test_descend_with_real_rotation_matches_field_log(self, executor):
        target = [REAL_LOW[0], REAL_LOW[1], REAL_LOW[2], 180.0, 0.0, 170.0]

        waypoints, order = self.build(executor, REAL_HIGH, target)

        assert order == '하강'
        assert labels(waypoints) == ['회전', 'X축', 'Y축', 'Z축']
        assert waypoints[0][1][:3] == pytest.approx(REAL_HIGH[:3])

    def test_negative_180_target_does_not_add_rotation_step(self, executor):
        target = [REAL_LOW[0], REAL_LOW[1], REAL_LOW[2], -180.0, 0.0, -180.0]

        waypoints, _ = self.build(executor, REAL_HIGH, target)

        assert labels(waypoints) == ['X축', 'Y축', 'Z축']


class TestSchemaRegistration:
    @pytest.mark.parametrize('job_type', ['move_to_point', 'go_home'])
    def test_option_declared_as_bool_default_false(self, job_type):
        param = RecipeManager.JOB_TYPES[job_type]['params']['decomposed_tcp']

        assert param['type'] == 'bool'
        assert param['default'] is False
