import pytest
from unittest.mock import MagicMock

from tm_msgs.srv import SetPositions

from tm_task_manager.services.coordinate_transformer import CoordinateTransformer
from tm_task_manager.services.teaching_service import TeachingService


# 공구가 기울어진 자세 — 공구 좌표계 조그였다면 병진 조그가 여러 베이스 축을 건드린다
TILTED_TCP = [100.0, -200.0, 300.0, 90.0, -22.0, -90.0]


@pytest.fixture
def node():
    n = MagicMock()
    n.current_tcp_pose = list(TILTED_TCP)
    return n


@pytest.fixture
def move_callback():
    return MagicMock(return_value=(True, "이동 완료"))


@pytest.fixture
def service(node):
    s = TeachingService(ros_node=node)
    s.last_jog_time = 0.0
    return s


def sent_target(move_callback):
    assert move_callback.call_count == 1
    call = move_callback.call_args_list[0]
    assert call.args[0] is SetPositions.Request.PTP_T
    return call.args[1]


def expected_service_format(target_mmdeg):
    return CoordinateTransformer.convert_tcp_to_service_format(target_mmdeg)


class TestJogBaseFrame:
    @pytest.mark.parametrize("axis,idx,direction", [
        ('x', 0, 1), ('x', 0, -1),
        ('y', 1, 1), ('y', 1, -1),
        ('z', 2, 1), ('z', 2, -1),
    ])
    def test_translation_moves_single_base_axis(self, service, move_callback,
                                                axis, idx, direction):
        step = 10.0
        success, _ = service.jog_tcp(
            axis, direction, step, 20.0,
            list(TILTED_TCP), list(TILTED_TCP[3:6]), move_callback
        )

        assert success is True
        expected = list(TILTED_TCP)
        expected[idx] += step * direction
        assert sent_target(move_callback) == pytest.approx(
            expected_service_format(expected))

    def test_orientation_unchanged_by_translation_jog(self, service, move_callback):
        service.jog_tcp('x', 1, 10.0, 20.0,
                        list(TILTED_TCP), list(TILTED_TCP[3:6]), move_callback)

        target = sent_target(move_callback)
        expected = expected_service_format(TILTED_TCP)
        assert target[3:6] == pytest.approx(expected[3:6])

    @pytest.mark.parametrize("axis,idx,direction", [
        ('x', 0, 1), ('y', 1, -1), ('z', 2, 1),
    ])
    def test_continuous_jog_matches_base_axis(self, service, move_callback,
                                              axis, idx, direction):
        step = 5.0
        success, _ = service.jog_tcp_continuous(
            axis, direction, step, 20.0,
            list(TILTED_TCP), list(TILTED_TCP[3:6]), move_callback
        )

        assert success is True
        expected = list(TILTED_TCP)
        expected[idx] += step * direction
        assert sent_target(move_callback) == pytest.approx(
            expected_service_format(expected))
