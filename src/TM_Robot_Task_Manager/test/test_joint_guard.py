"""safety 조인트 한계(check_joints·JointGuard 자동정지 latch)를 검증한다."""
from unittest.mock import MagicMock

from tm_task_manager.safety import safety_area as sa
from tm_task_manager.safety.joint_guard import JointGuard

INSIDE = [0.0, 0.0, 0.0, 0.0, 90.0, 0.0]


def _area(**overrides):
    area = {k: (dict(v) if isinstance(v, dict) else v)
            for k, v in sa.DEFAULT_AREA.items()}
    jl = {k: (dict(v) if isinstance(v, dict) else v)
          for k, v in sa.DEFAULT_JOINT_LIMITS.items()}
    jl['enabled'] = True
    jl.update(overrides)
    area['joint_limits'] = jl
    return area


def test_default_limits_match_tm20_conservative():
    limits = sa.DEFAULT_JOINT_LIMITS['limits_deg']
    assert limits['j1'] == [-270.0, 270.0]
    assert limits['j2'] == [-180.0, 180.0]
    assert limits['j3'] == [-163.0, 163.0]
    assert limits['j6'] == [-270.0, 270.0]
    assert sa.DEFAULT_JOINT_LIMITS['margin_deg'] == 5.0
    assert sa.DEFAULT_JOINT_LIMITS['auto_stop'] is True


def test_check_joints_inside_ok():
    ok, reason = sa.check_joints(_area(), INSIDE)
    assert ok, reason


def test_check_joints_margin_violation():
    joints = list(INSIDE)
    joints[2] = 159.0
    ok, reason = sa.check_joints(_area(), joints)
    assert not ok
    assert 'J3' in reason and '158' in reason


def test_check_joints_disabled_passes():
    joints = [300.0] * 6
    ok, _ = sa.check_joints(_area(enabled=False), joints)
    assert ok


def test_guard_stops_once_and_rearms():
    stop = MagicMock()
    logs = []
    guard = JointGuard(_area(), stop_fn=stop, log_callback=logs.append)

    bad = list(INSIDE)
    bad[0] = 268.0
    assert guard.update(bad) is not None
    assert guard.update(bad) is not None
    stop.assert_called_once()

    near = list(INSIDE)
    near[0] = 264.5
    assert guard.update(near) is None
    assert guard.update(bad) is not None
    stop.assert_called_once()

    assert guard.update(INSIDE) is None
    assert guard.update(bad) is not None
    assert stop.call_count == 2


def test_guard_auto_stop_off_logs_only():
    stop = MagicMock()
    guard = JointGuard(_area(auto_stop=False), stop_fn=stop, log_callback=lambda m: None)
    bad = list(INSIDE)
    bad[5] = -269.0
    assert guard.update(bad) is not None
    stop.assert_not_called()


def test_validate_joint_limits():
    ok, _ = sa.validate_joint_limits(_area())
    assert ok

    bad = _area()
    bad['joint_limits']['limits_deg']['j2'] = [180.0, -180.0]
    ok, reason = sa.validate_joint_limits(bad)
    assert not ok and 'j2' in reason

    wide = _area(margin_deg=400.0)
    ok, reason = sa.validate_joint_limits(wide)
    assert not ok and 'margin' in reason
