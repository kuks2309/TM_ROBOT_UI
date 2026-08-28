import sys
import types
from unittest.mock import MagicMock

import pytest

from tm_task_manager.services.gripper_override_service import GripperOverrideService


class _Node:
    def __init__(self, smc=None, schunk=None):
        self.gripper_action_client = smc
        self.schunk_gripper_client = schunk


def _smc_client(*, server=True, accepted=True, result_code=0, message=''):
    c = MagicMock()
    c.wait_for_server.return_value = server
    handle = MagicMock()
    handle.accepted = accepted
    result = MagicMock()
    result.result_code = result_code
    result.message = message
    wrapped = MagicMock()
    wrapped.result = result
    send_future, result_future = MagicMock(), MagicMock()
    send_future.done.return_value = True
    send_future.result.return_value = handle
    result_future.done.return_value = True
    result_future.result.return_value = wrapped
    c.send_goal_async.return_value = send_future
    handle.get_result_async.return_value = result_future
    return c


def _schunk_client(*, service=True, received=True):
    c = MagicMock()
    c.wait_for_service.return_value = service
    fut = MagicMock()
    fut.done.return_value = True
    res = MagicMock()
    res.received = received
    fut.result.return_value = res
    c.call_async.return_value = fut
    return c


@pytest.fixture(autouse=True)
def _stub_msgs(monkeypatch):
    gr = types.ModuleType('gripper_ros')
    gra = types.ModuleType('gripper_ros.action')
    goal = MagicMock()
    goal.COMMAND_PROFILE = 1
    gra.GripperCommand = MagicMock(Goal=MagicMock(return_value=goal, COMMAND_PROFILE=1))
    gra.GripperCommand.Goal.COMMAND_PROFILE = 1
    tc = types.ModuleType('tc_msgs')
    tcs = types.ModuleType('tc_msgs.srv')
    tcs.GripperCommand = MagicMock(Request=MagicMock(return_value=MagicMock()))
    for name, mod in (('gripper_ros', gr), ('gripper_ros.action', gra),
                      ('tc_msgs', tc), ('tc_msgs.srv', tcs)):
        monkeypatch.setitem(sys.modules, name, mod)
    monkeypatch.setattr(
        'tm_task_manager.services.gripper_override_service.rclpy',
        MagicMock(), raising=True)
    yield


def _svc(node):
    logs = []
    return GripperOverrideService(node, log_callback=logs.append), logs


def test_backends_lists_smc_first():
    svc, _ = _svc(_Node(smc=_smc_client(), schunk=_schunk_client()))
    assert svc.backends() == ['SMC', 'SCHUNK']
    assert svc.available()


def test_schunk_only_machine_is_available():
    svc, _ = _svc(_Node(schunk=_schunk_client()))
    assert svc.backends() == ['SCHUNK']
    assert svc.available()


def test_no_backend_is_unavailable_with_reason():
    svc, _ = _svc(_Node())
    assert not svc.available()
    assert svc.backends() == []
    assert '없습니다' in svc.unavailable_reason()


def test_available_machine_has_no_unavailable_reason():
    svc, _ = _svc(_Node(schunk=_schunk_client()))
    assert svc.unavailable_reason() == ''


def test_no_backend_sends_nothing():
    node = _Node()
    svc, logs = _svc(node)
    ok, reason = svc.force_release()
    assert ok is False
    assert '실행하지 않았습니다' in reason
    assert any('실행하지 않았습니다' in m for m in logs), "사유를 로그로 알려야 한다"


def test_missing_node_sends_nothing():
    svc, logs = _svc(None)
    ok, reason = svc.force_release()
    assert ok is False and '실행하지 않았습니다' in reason


def test_smc_used_when_present():
    smc = _smc_client()
    svc, _ = _svc(_Node(smc=smc, schunk=_schunk_client()))
    ok, reason = svc.force_release()
    assert ok and 'SMC' in reason
    smc.send_goal_async.assert_called_once()


def test_falls_back_to_schunk_when_smc_absent():
    schunk = _schunk_client()
    svc, _ = _svc(_Node(schunk=schunk))
    ok, reason = svc.force_release()
    assert ok and 'SCHUNK' in reason
    schunk.call_async.assert_called_once()


def test_falls_back_when_smc_server_missing():
    smc = _smc_client(server=False)
    schunk = _schunk_client()
    svc, _ = _svc(_Node(smc=smc, schunk=schunk))
    ok, reason = svc.force_release()
    assert ok and 'SCHUNK' in reason
    smc.send_goal_async.assert_not_called()


def test_does_not_fall_back_when_smc_present_but_fails():
    smc = _smc_client(accepted=False)
    schunk = _schunk_client()
    svc, _ = _svc(_Node(smc=smc, schunk=schunk))
    ok, reason = svc.force_release()
    assert ok is False
    assert reason.startswith('SMC:')
    schunk.call_async.assert_not_called(), "SCHUNK 로 흘러가면 안 된다"


def test_does_not_fall_back_when_smc_returns_error_code():
    smc = _smc_client(result_code=7, message='InterlockRejected')
    schunk = _schunk_client()
    svc, _ = _svc(_Node(smc=smc, schunk=schunk))
    ok, reason = svc.force_release()
    assert ok is False and 'result_code=7' in reason
    schunk.call_async.assert_not_called()


def test_schunk_service_missing_reports_no_backend():
    schunk = _schunk_client(service=False)
    svc, _ = _svc(_Node(schunk=schunk))
    ok, reason = svc.force_release()
    assert ok is False
    assert '실행하지 않았습니다' in reason
    schunk.call_async.assert_not_called()


def test_schunk_not_received_is_failure():
    schunk = _schunk_client(received=False)
    svc, _ = _svc(_Node(schunk=schunk))
    ok, reason = svc.force_release()
    assert ok is False and reason.startswith('SCHUNK:')


def test_schunk_success_message_states_its_limit():
    svc, _ = _svc(_Node(schunk=_schunk_client()))
    ok, reason = svc.force_release()
    assert ok and '수신 확인' in reason


def test_smc_sets_bypass_interlock():
    smc = _smc_client()
    svc, _ = _svc(_Node(smc=smc))
    svc.force_release()
    goal = smc.send_goal_async.call_args[0][0]
    assert goal.bypass_interlock is True
    assert goal.profile == 'release'
