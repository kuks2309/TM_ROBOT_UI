import pytest
from unittest.mock import MagicMock

from tm_msgs.srv import SetPositions

from tm_task_manager.services.teaching_service import TeachingService
from tm_task_manager.services.decomposed_move_planner import (
    build_decomposed_tcp_waypoints,
)


TCP = [-238.28, 198.46, 297.41, 180.0, 0.0, 180.0]


@pytest.fixture
def node():
    n = MagicMock()
    n.current_tcp_pose = list(TCP)
    return n


@pytest.fixture
def move_callback():
    return MagicMock(return_value=(True, "이동 완료"))


@pytest.fixture
def service(node):
    return TeachingService(ros_node=node)


def sent_motion_types(move_callback):
    return [call.args[0] for call in move_callback.call_args_list]


def sent_positions(move_callback):
    return [call.args[1] for call in move_callback.call_args_list]


class TestTeachingMoveDecomposed:
    def test_option_off_sends_single_ptp(self, service, move_callback):
        success, _ = service.move_to_position(
            'tcp', [-268.28, 188.46, 247.41, 180.0, 0.0, 180.0], 10.0, move_callback
        )

        assert success is True
        assert sent_motion_types(move_callback) == [SetPositions.Request.PTP_T]

    def test_option_on_splits_into_line_t_steps(self, service, move_callback):
        success, msg = service.move_to_position(
            'tcp', [-268.28, 188.46, 247.41, 180.0, 0.0, 180.0], 10.0, move_callback,
            decomposed_tcp=True
        )

        assert success is True
        types = sent_motion_types(move_callback)
        assert len(types) == 3
        for motion_type in types:
            assert motion_type is SetPositions.Request.LINE_T
        assert '하강' in msg

    def test_descending_moves_z_last(self, service, move_callback):
        service.move_to_position(
            'tcp', [-268.28, 188.46, 247.41, 180.0, 0.0, 180.0], 10.0, move_callback,
            decomposed_tcp=True
        )

        positions = sent_positions(move_callback)
        assert positions[0][:3] == pytest.approx([-0.26828, 0.19846, 0.29741])
        assert positions[1][:3] == pytest.approx([-0.26828, 0.18846, 0.29741])
        assert positions[2][:3] == pytest.approx([-0.26828, 0.18846, 0.24741])

    def test_ascending_moves_z_first(self, service, move_callback, node):
        node.current_tcp_pose = [-268.28, 188.46, 247.41, 180.0, 0.0, 180.0]

        service.move_to_position(
            'tcp', [-238.28, 198.46, 297.41, 180.0, 0.0, 180.0], 10.0, move_callback,
            decomposed_tcp=True
        )

        positions = sent_positions(move_callback)
        assert len(positions) == 3
        assert positions[0][:3] == pytest.approx([-0.26828, 0.18846, 0.29741])

    def test_rotation_step_comes_first(self, service, move_callback):
        service.move_to_position(
            'tcp', [-268.28, 188.46, 247.41, 180.0, 0.0, 170.0], 10.0, move_callback,
            decomposed_tcp=True
        )

        positions = sent_positions(move_callback)
        assert len(positions) == 4
        assert positions[0][:3] == pytest.approx([-0.23828, 0.19846, 0.29741])

    def test_no_rotation_step_across_180_wrap(self, service, move_callback, node):
        node.current_tcp_pose = [-238.28, 198.46, 297.41, -179.99981689453125, 0.0, 179.9998779296875]

        service.move_to_position(
            'tcp', [-268.28, 188.46, 247.41, 180.0, 0.0, 180.0], 10.0, move_callback,
            decomposed_tcp=True
        )

        assert len(sent_positions(move_callback)) == 3

    def test_joint_mode_ignores_option(self, service, move_callback):
        service.move_to_position(
            'joint', [0.0, 0.0, 90.0, 0.0, 90.0, 0.0], 10.0, move_callback,
            decomposed_tcp=True
        )

        assert sent_motion_types(move_callback) == [SetPositions.Request.PTP_J]

    def test_aborts_remaining_steps_on_failure(self, service):
        callback = MagicMock(return_value=(False, "LINE_T 거절"))

        success, msg = service.move_to_position(
            'tcp', [-268.28, 188.46, 247.41, 180.0, 0.0, 180.0], 10.0, callback,
            decomposed_tcp=True
        )

        assert success is False
        assert callback.call_count == 1
        assert '실패' in msg

    def test_fails_when_tcp_pose_unavailable(self, service, move_callback, node):
        node.current_tcp_pose = None

        success, _ = service.move_to_position(
            'tcp', [-268.28, 188.46, 247.41, 180.0, 0.0, 180.0], 10.0, move_callback,
            decomposed_tcp=True
        )

        assert success is False
        assert move_callback.call_count == 0

    def test_no_command_when_already_at_target(self, service, move_callback):
        success, _ = service.move_to_position(
            'tcp', list(TCP), 10.0, move_callback, decomposed_tcp=True
        )

        assert success is True
        assert move_callback.call_count == 0

    def test_velocity_forwarded_to_every_step(self, service, move_callback):
        service.move_to_position(
            'tcp', [-268.28, 188.46, 247.41, 180.0, 0.0, 180.0], 33.0, move_callback,
            decomposed_tcp=True
        )

        for call in move_callback.call_args_list:
            assert call.args[2] == 33.0


class TestPlannerSharedBySequenceAndTeaching:
    def test_job_executor_delegates_to_shared_planner(self):
        from tm_task_manager.job_executor import JobExecutor

        executor = JobExecutor(ros_node=MagicMock())
        current = [-238.28, 198.46, 297.41, 180.0, 0.0, 180.0]
        target = [-268.28, 188.46, 247.41, 180.0, 0.0, 170.0]

        from_executor = executor._build_decomposed_tcp_waypoints(current, target)
        from_planner = build_decomposed_tcp_waypoints(current, target)

        assert from_executor == from_planner
