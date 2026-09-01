"""CommandGate 의 명령 직렬화(획득/해제/거부 로그)와 JogService 의 게이트 연동을 검증한다."""
import pytest

from tm_task_manager.services.command_gate import CommandGate
from tm_task_manager.services.jog_service import JogService


@pytest.fixture
def logs():
    return []


@pytest.fixture
def gate(logs):
    return CommandGate(log_callback=logs.append)


def test_first_acquire_succeeds(gate):
    assert gate.acquire("조그 x+") is True
    assert gate.busy is True
    assert gate.current_label == "조그 x+"


def test_second_acquire_is_rejected_while_busy(gate):
    gate.acquire("첫 명령")
    assert gate.acquire("두 번째") is False
    assert gate.acquire("세 번째") is False
    assert gate.rejected_count == 2


def test_release_allows_next_command(gate):
    gate.acquire("첫 명령")
    gate.release()
    assert gate.busy is False
    assert gate.acquire("다음 명령") is True


def test_rejection_is_logged_once_on_release(gate, logs):
    gate.acquire("Task 수동 실행")
    for _ in range(10):
        gate.acquire("스팸")

    assert logs == []

    gate.release()
    assert len(logs) == 1
    assert "10건" in logs[0]
    assert "Task 수동 실행" in logs[0]


def test_no_log_when_nothing_was_rejected(gate, logs):
    gate.acquire("명령")
    gate.release()
    assert logs == []


def test_rejected_count_resets_after_release(gate):
    gate.acquire("명령")
    gate.acquire("스팸")
    gate.release()
    assert gate.rejected_count == 0


def test_release_without_acquire_is_noop(gate, logs):
    gate.release()
    assert gate.busy is False
    assert logs == []


def test_run_executes_and_releases(gate):
    assert gate.run("명령", lambda: "결과") == "결과"
    assert gate.busy is False


def test_run_releases_even_on_exception(gate):
    def boom():
        raise RuntimeError("모션 실패")

    with pytest.raises(RuntimeError):
        gate.run("명령", boom)

    assert gate.busy is False
    assert gate.acquire("다음") is True


def test_run_skips_when_busy(gate):
    calls = []
    gate.acquire("실행 중")
    assert gate.run("끼어든 명령", lambda: calls.append(1)) is None
    assert calls == []


def test_nested_command_is_rejected(gate):
    inner_ran = []

    def outer():
        gate.run("안쪽", lambda: inner_ran.append(1))
        return "바깥 완료"

    assert gate.run("바깥", outer) == "바깥 완료"
    assert inner_ran == []


class _FakeTeachingService:
    def __init__(self):
        self.calls = []

    def jog_tcp(self, axis, direction, *args, **kwargs):
        self.calls.append((axis, direction))
        return True, "조그 완료"

    def jog_tcp_continuous(self, axis, direction, *args, **kwargs):
        self.calls.append(('cont', axis, direction))
        return True, "연속 조그 완료"


class _FakeNode:
    current_tcp_pose = [0.0, 0.0, 400.0, 180.0, 0.0, 0.0]


def _jog_service(gate):
    return JogService(
        ros_node=_FakeNode(),
        teaching_service=_FakeTeachingService(),
        move_callback=lambda *a, **k: (True, ""),
        command_gate=gate,
    )


def test_jog_runs_when_gate_is_free(gate):
    service = _jog_service(gate)
    assert service.jog('x', 1) is True
    assert service._teaching_service.calls == [('x', 1)]


def test_jog_is_blocked_while_gate_is_busy(gate):
    service = _jog_service(gate)
    gate.acquire("앞선 명령")

    assert service.jog('x', 1) is False
    assert service.jog('y', -1) is False
    assert service._teaching_service.calls == []
    assert gate.rejected_count == 2


def test_jog_continuous_is_blocked_while_gate_is_busy(gate):
    service = _jog_service(gate)
    gate.acquire("앞선 명령")

    assert service.jog_continuous('z', -1) is False
    assert service._teaching_service.calls == []


def test_jog_releases_gate_after_completion(gate):
    service = _jog_service(gate)
    service.jog('x', 1)
    assert gate.busy is False
    assert service.jog('x', -1) is True


def test_jog_works_without_gate():
    service = JogService(
        ros_node=_FakeNode(),
        teaching_service=_FakeTeachingService(),
        move_callback=lambda *a, **k: (True, ""),
    )
    assert service.jog('x', 1) is True
