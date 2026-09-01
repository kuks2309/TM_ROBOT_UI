"""이동 완료 대기 한도의 거리·속도 기반 추정(estimate_motion_timeout_s) 검증."""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tm_task_manager.services.coordinate_transformer import (  # noqa: E402
    MOTION_TIMEOUT_BASE_S, MOTION_TIMEOUT_MARGIN, MOTION_TIMEOUT_MAX_S, MOTION_TIMEOUT_MIN_S,
    MAX_JOINT_VELOCITY, MAX_TCP_SPEED, estimate_motion_timeout_s,
)

HOME_TCP = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


def test_unknown_current_pose_falls_back_to_min():
    assert estimate_motion_timeout_s('tcp', [1.0] * 6, 10.0) == MOTION_TIMEOUT_MIN_S
    assert estimate_motion_timeout_s('joint', [1.0] * 6, 10.0, current_tcp_mm_deg=HOME_TCP) == MOTION_TIMEOUT_MIN_S


def test_short_move_keeps_min_floor():
    # 50mm 를 100% 속도로 — 예상 0.05s → BASE 10s 근처지만 하한 30s 가 유지된다
    target = [0.05, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert estimate_motion_timeout_s('line', target, 100.0, current_tcp_mm_deg=HOME_TCP) == MOTION_TIMEOUT_MIN_S


def test_long_slow_line_move_exceeds_old_fixed_limit():
    # 1.5m 를 5% 속도(0.05 m/s)로 — 예상 30s → 10 + 3×30 = 100s (종전 고정 30s 면 실패하던 경우)
    target = [1.5, 0.0, 0.0, 0.0, 0.0, 0.0]
    t = estimate_motion_timeout_s('line', target, 5.0, current_tcp_mm_deg=HOME_TCP)
    expected = MOTION_TIMEOUT_BASE_S + MOTION_TIMEOUT_MARGIN * (1.5 / (0.05 * MAX_TCP_SPEED))
    assert math.isclose(t, expected)
    assert t > 30.0


def test_upper_bound_clamps_absurd_estimates():
    target = [10.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # 10m 를 1% 속도로
    assert estimate_motion_timeout_s('line', target, 1.0, current_tcp_mm_deg=HOME_TCP) == MOTION_TIMEOUT_MAX_S


def test_zero_velocity_does_not_divide_by_zero():
    target = [0.5, 0.0, 0.0, 0.0, 0.0, 0.0]
    t = estimate_motion_timeout_s('tcp', target, 0.0, current_tcp_mm_deg=HOME_TCP)
    assert MOTION_TIMEOUT_MIN_S <= t <= MOTION_TIMEOUT_MAX_S


def test_rotation_only_tcp_move_uses_joint_speed_bound():
    # 위치 동일, rz 180° 회전을 10% 속도로 — 회전 추정이 병진(0) 을 이겨야 한다
    target = [0.0, 0.0, 0.0, 0.0, 0.0, math.pi]
    t = estimate_motion_timeout_s('tcp', target, 10.0, current_tcp_mm_deg=HOME_TCP)
    expected = MOTION_TIMEOUT_BASE_S + MOTION_TIMEOUT_MARGIN * (math.pi / (0.1 * MAX_JOINT_VELOCITY))
    assert math.isclose(t, min(expected, MOTION_TIMEOUT_MAX_S))


def test_joint_move_uses_largest_joint_delta():
    current_deg = [0.0, -30.0, 120.0, 0.0, 90.0, 0.0]
    target_rad = [math.radians(v) for v in [90.0, -30.0, 120.0, 0.0, 90.0, 0.0]]  # J1 만 90° 이동
    t = estimate_motion_timeout_s('joint', target_rad, 20.0, current_joint_deg=current_deg)
    expected = MOTION_TIMEOUT_BASE_S + MOTION_TIMEOUT_MARGIN * (math.radians(90.0) / (0.2 * MAX_JOINT_VELOCITY))
    assert math.isclose(t, max(MOTION_TIMEOUT_MIN_S, expected))
