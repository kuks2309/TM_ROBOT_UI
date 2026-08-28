import math
import numpy as np
import pytest

from tm_task_manager.tools.jig_plane_calculator import (
    JigPlaneCalculator,
    Mark,
    MIN_KEEP_PROJECTION,
    TOOL_OFFSET_KEYS,
    _rotation_matrix_from_pose,
    apply_tool_offset,
    plane_normal_from_pose,
    signed_point_to_plane_distance,
    tcp_pose_for_plane_normal,
    tool_offset_from_poses,
)

ANGLE_TOL = 1e-6
VECTOR_TOL = 1e-9


def _horizontal_plane(x=0.0, y=0.0, z=0.0):
    return {'x': x, 'y': y, 'z': z, 'rx': 0.0, 'ry': 0.0, 'rz': 0.0}


def _tool_z_axis(pose):
    return _rotation_matrix_from_pose(pose)[:, 2]


def _angle_gap_deg(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def test_normal_of_horizontal_plane_is_base_z():
    assert np.allclose(plane_normal_from_pose(_horizontal_plane()), [0, 0, 1], atol=VECTOR_TOL)


def test_normal_of_flipped_plane_points_down():
    pose = {'x': 0, 'y': 0, 'z': 0, 'rx': 180.0, 'ry': 0.0, 'rz': 0.0}
    assert np.allclose(plane_normal_from_pose(pose), [0, 0, -1], atol=VECTOR_TOL)


def test_normal_of_tilted_plane_matches_analytic():
    pose = {'x': 0, 'y': 0, 'z': 0, 'rx': 0.0, 'ry': 30.0, 'rz': 0.0}
    expected = [math.sin(math.radians(30)), 0.0, math.cos(math.radians(30))]
    assert np.allclose(plane_normal_from_pose(pose), expected, atol=1e-12)


def test_normal_is_unit_length():
    pose = {'x': 10, 'y': -20, 'z': 30, 'rx': 12.0, 'ry': -34.0, 'rz': 56.0}
    assert np.linalg.norm(plane_normal_from_pose(pose)) == pytest.approx(1.0)


def test_distance_above_horizontal_plane_is_positive():
    plane = _horizontal_plane(z=100.0)
    assert signed_point_to_plane_distance((0, 0, 200.0), plane) == pytest.approx(100.0)


def test_distance_below_horizontal_plane_is_negative():
    plane = _horizontal_plane(z=100.0)
    assert signed_point_to_plane_distance((0, 0, 50.0), plane) == pytest.approx(-50.0)


def test_distance_on_plane_is_zero():
    plane = _horizontal_plane(z=100.0)
    assert signed_point_to_plane_distance((500.0, -300.0, 100.0), plane) == pytest.approx(0.0)


def test_distance_ignores_lateral_offset():
    plane = _horizontal_plane(z=0.0)
    near = signed_point_to_plane_distance((0, 0, 75.0), plane)
    far = signed_point_to_plane_distance((9999.0, -9999.0, 75.0), plane)
    assert near == pytest.approx(far)


def test_distance_on_tilted_plane_matches_analytic():
    plane = {'x': 100.0, 'y': 200.0, 'z': 300.0, 'rx': 0.0, 'ry': 30.0, 'rz': 0.0}
    normal = plane_normal_from_pose(plane)
    point = np.array([100.0, 200.0, 300.0]) + normal * 40.0
    assert signed_point_to_plane_distance(tuple(point), plane) == pytest.approx(40.0)


def test_target_position_is_center_plus_normal_times_standoff():
    plane = _horizontal_plane(x=10.0, y=20.0, z=30.0)
    target = tcp_pose_for_plane_normal(plane, standoff_mm=150.0, rz_mode='plane')
    assert (target['x'], target['y'], target['z']) == pytest.approx((10.0, 20.0, 180.0))


def test_target_position_on_tilted_plane_follows_normal():
    plane = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'rx': 0.0, 'ry': 30.0, 'rz': 0.0}
    target = tcp_pose_for_plane_normal(plane, standoff_mm=100.0, rz_mode='plane')
    expected = plane_normal_from_pose(plane) * 100.0
    assert (target['x'], target['y'], target['z']) == pytest.approx(tuple(expected))


def test_target_distance_equals_standoff():
    plane = {'x': -50.0, 'y': 80.0, 'z': 120.0, 'rx': 5.0, 'ry': -12.0, 'rz': 40.0}
    target = tcp_pose_for_plane_normal(plane, standoff_mm=175.0, rz_mode='plane')
    distance = signed_point_to_plane_distance(
        (target['x'], target['y'], target['z']), plane
    )
    assert distance == pytest.approx(175.0)


def test_tool_z_opposes_normal_on_horizontal_plane():
    plane = _horizontal_plane()
    target = tcp_pose_for_plane_normal(plane, standoff_mm=150.0, rz_mode='plane')
    assert np.allclose(_tool_z_axis(target), -plane_normal_from_pose(plane), atol=1e-9)


def test_tool_z_opposes_normal_on_tilted_plane():
    plane = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'rx': 8.0, 'ry': -25.0, 'rz': 70.0}
    target = tcp_pose_for_plane_normal(plane, standoff_mm=150.0, rz_mode='plane')
    assert np.allclose(_tool_z_axis(target), -plane_normal_from_pose(plane), atol=1e-9)


def test_tool_z_opposes_normal_in_keep_mode():
    plane = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'rx': -15.0, 'ry': 20.0, 'rz': -60.0}
    current = [0.0, 0.0, 500.0, 180.0, 0.0, 30.0]
    target = tcp_pose_for_plane_normal(plane, standoff_mm=120.0, rz_mode='keep',
                                       current_tcp=current)
    assert np.allclose(_tool_z_axis(target), -plane_normal_from_pose(plane), atol=1e-9)


def test_result_orientation_is_orthonormal():
    plane = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'rx': 3.0, 'ry': -40.0, 'rz': 100.0}
    target = tcp_pose_for_plane_normal(plane, standoff_mm=90.0, rz_mode='plane')
    rotation = _rotation_matrix_from_pose(target)
    assert np.allclose(rotation @ rotation.T, np.eye(3), atol=1e-9)
    assert np.linalg.det(rotation) == pytest.approx(1.0)


def test_keep_mode_preserves_current_rz_when_already_perpendicular():
    plane = _horizontal_plane()
    current = [0.0, 0.0, 400.0, 180.0, 0.0, 45.0]
    target = tcp_pose_for_plane_normal(plane, standoff_mm=150.0, rz_mode='keep',
                                       current_tcp=current)
    assert target['rz'] == pytest.approx(45.0, abs=ANGLE_TOL)
    assert target['rx'] == pytest.approx(180.0, abs=ANGLE_TOL)
    assert target['ry'] == pytest.approx(0.0, abs=ANGLE_TOL)


def test_plane_mode_ignores_current_tcp():
    plane = _horizontal_plane()
    first = tcp_pose_for_plane_normal(plane, standoff_mm=150.0, rz_mode='plane',
                                      current_tcp=[0, 0, 0, 180.0, 0.0, 45.0])
    second = tcp_pose_for_plane_normal(plane, standoff_mm=150.0, rz_mode='plane',
                                       current_tcp=[0, 0, 0, 180.0, 0.0, -90.0])
    assert first == second


def test_keep_and_plane_modes_differ_in_rz_only():
    plane = _horizontal_plane()
    current = [0.0, 0.0, 400.0, 180.0, 0.0, 45.0]
    keep = tcp_pose_for_plane_normal(plane, 150.0, 'keep', current)
    plane_mode = tcp_pose_for_plane_normal(plane, 150.0, 'plane')
    assert np.allclose(_tool_z_axis(keep), _tool_z_axis(plane_mode), atol=1e-9)
    assert keep['rz'] != pytest.approx(plane_mode['rz'], abs=1e-3)


def test_keep_mode_falls_back_when_current_x_parallel_to_normal():
    plane = _horizontal_plane()
    current = [0.0, 0.0, 400.0, 0.0, 90.0, 0.0]
    projection = np.linalg.norm(
        _rotation_matrix_from_pose({'rx': 0.0, 'ry': 90.0, 'rz': 0.0})[:, 0]
        - np.dot(_rotation_matrix_from_pose({'rx': 0.0, 'ry': 90.0, 'rz': 0.0})[:, 0],
                 [0, 0, -1]) * np.array([0, 0, -1])
    )
    assert projection < MIN_KEEP_PROJECTION

    keep = tcp_pose_for_plane_normal(plane, 150.0, 'keep', current)
    plane_mode = tcp_pose_for_plane_normal(plane, 150.0, 'plane')

    assert np.allclose(_tool_z_axis(keep), _tool_z_axis(plane_mode), atol=1e-9)
    assert (keep['x'], keep['y'], keep['z']) == pytest.approx(
        (plane_mode['x'], plane_mode['y'], plane_mode['z'])
    )
    assert _angle_gap_deg(plane_mode['rz'], keep['rz']) == pytest.approx(90.0, abs=ANGLE_TOL)


def test_plane_mode_follows_plane_long_side_not_short_side():
    plane = _horizontal_plane()
    plane_rotation = _rotation_matrix_from_pose(plane)

    target = tcp_pose_for_plane_normal(plane, standoff_mm=150.0, rz_mode='plane')
    tool_x = _rotation_matrix_from_pose(target)[:, 0]

    assert np.allclose(tool_x, plane_rotation[:, 1], atol=1e-9)


def test_plane_mode_is_90deg_from_plane_x_axis_on_tilted_plane():
    plane = {'x': 12.0, 'y': -30.0, 'z': 45.0, 'rx': 6.0, 'ry': -18.0, 'rz': 25.0}
    target = tcp_pose_for_plane_normal(plane, standoff_mm=150.0, rz_mode='plane')

    tool_x = _rotation_matrix_from_pose(target)[:, 0]
    plane_x = _rotation_matrix_from_pose(plane)[:, 0]
    plane_y = _rotation_matrix_from_pose(plane)[:, 1]

    assert np.dot(tool_x, plane_x) == pytest.approx(0.0, abs=1e-9)
    assert np.allclose(tool_x, plane_y, atol=1e-9)


def test_tool_offset_zero_keeps_pose():
    base = {'x': 100.0, 'y': -50.0, 'z': 300.0, 'rx': 175.0, 'ry': 3.0, 'rz': -20.0}
    result = apply_tool_offset(base, {k: 0.0 for k in TOOL_OFFSET_KEYS})
    for key in ('x', 'y', 'z', 'rx', 'ry', 'rz'):
        assert result[key] == pytest.approx(base[key], abs=1e-9)


def test_tool_offset_translation_is_in_tool_frame():
    base = {'x': 0.0, 'y': 0.0, 'z': 500.0, 'rx': 180.0, 'ry': 0.0, 'rz': 0.0}
    result = apply_tool_offset(base, {'x': 10.0, 'y': 4.0})

    assert result['x'] == pytest.approx(10.0, abs=1e-9)
    assert result['y'] == pytest.approx(-4.0, abs=1e-9)
    assert result['z'] == pytest.approx(500.0, abs=1e-9)


def test_tool_offset_has_no_z_axis():
    base = {'x': 0.0, 'y': 0.0, 'z': 500.0, 'rx': 180.0, 'ry': 0.0, 'rz': 0.0}
    result = apply_tool_offset(base, {'z': 999.0})

    assert result['z'] == pytest.approx(500.0, abs=1e-9)
    assert 'z' not in TOOL_OFFSET_KEYS


def test_tool_offset_rz_rotates_about_tool_axis():
    base = {'x': 0.0, 'y': 0.0, 'z': 500.0, 'rx': 180.0, 'ry': 0.0, 'rz': 10.0}
    result = apply_tool_offset(base, {'rz': 90.0})

    assert np.allclose(_tool_z_axis(result), _tool_z_axis(base), atol=1e-9)
    assert _angle_gap_deg(result['rz'], base['rz']) == pytest.approx(90.0, abs=ANGLE_TOL)


def test_tool_offset_roundtrip_recovers_offset():
    base = {'x': 120.0, 'y': -80.0, 'z': 400.0, 'rx': 170.0, 'ry': -8.0, 'rz': 35.0}
    offset = {'x': 7.5, 'y': -3.25, 'rx': 2.0, 'ry': -1.5, 'rz': 12.0}

    actual = apply_tool_offset(base, offset)
    recovered, z_ignored = tool_offset_from_poses(base, actual)

    for key in TOOL_OFFSET_KEYS:
        assert recovered[key] == pytest.approx(offset[key], abs=1e-6)
    assert z_ignored == pytest.approx(0.0, abs=1e-9)


def test_tool_offset_from_poses_reports_ignored_z_gap():
    base = {'x': 0.0, 'y': 0.0, 'z': 500.0, 'rx': 180.0, 'ry': 0.0, 'rz': 0.0}
    actual = dict(base, z=480.0)

    offset, z_ignored = tool_offset_from_poses(base, actual)

    assert z_ignored == pytest.approx(20.0, abs=1e-9)
    assert offset['x'] == pytest.approx(0.0, abs=1e-9)
    assert offset['y'] == pytest.approx(0.0, abs=1e-9)


def test_rejects_non_positive_standoff():
    with pytest.raises(ValueError, match="standoff_mm"):
        tcp_pose_for_plane_normal(_horizontal_plane(), standoff_mm=0.0, rz_mode='plane')
    with pytest.raises(ValueError, match="standoff_mm"):
        tcp_pose_for_plane_normal(_horizontal_plane(), standoff_mm=-10.0, rz_mode='plane')


def test_rejects_unknown_rz_mode():
    with pytest.raises(ValueError, match="rz_mode"):
        tcp_pose_for_plane_normal(_horizontal_plane(), standoff_mm=100.0, rz_mode='auto')


def test_rejects_keep_mode_without_current_tcp():
    with pytest.raises(ValueError, match="current_tcp"):
        tcp_pose_for_plane_normal(_horizontal_plane(), standoff_mm=100.0, rz_mode='keep')
    with pytest.raises(ValueError, match="current_tcp"):
        tcp_pose_for_plane_normal(_horizontal_plane(), standoff_mm=100.0, rz_mode='keep',
                                  current_tcp=[0.0, 0.0, 0.0])


def test_existing_calculate_plane_pose_still_flat_for_flat_marks():
    calc = JigPlaneCalculator()
    calc.load_from_marks([
        Mark(x=0.0,   y=0.0,   z=0.0, rx=0.0, ry=0.0, rz=0.0),
        Mark(x=0.0,   y=100.0, z=0.0, rx=0.0, ry=0.0, rz=0.0),
        Mark(x=200.0, y=0.0,   z=0.0, rx=0.0, ry=0.0, rz=0.0),
        Mark(x=200.0, y=100.0, z=0.0, rx=0.0, ry=0.0, rz=0.0),
    ])
    pose = calc.to_dict()
    assert (pose['x'], pose['y'], pose['z']) == pytest.approx((100.0, 50.0, 0.0))
    assert pose['rx'] == pytest.approx(0.0, abs=ANGLE_TOL)
    assert pose['ry'] == pytest.approx(0.0, abs=ANGLE_TOL)
    assert pose['rz'] == pytest.approx(0.0, abs=ANGLE_TOL)


def test_flat_marks_yield_upward_normal():
    calc = JigPlaneCalculator()
    calc.load_from_marks([
        Mark(x=0.0,   y=0.0,   z=0.0, rx=0.0, ry=0.0, rz=0.0),
        Mark(x=0.0,   y=100.0, z=0.0, rx=0.0, ry=0.0, rz=0.0),
        Mark(x=200.0, y=0.0,   z=0.0, rx=0.0, ry=0.0, rz=0.0),
        Mark(x=200.0, y=100.0, z=0.0, rx=0.0, ry=0.0, rz=0.0),
    ])
    assert np.allclose(plane_normal_from_pose(calc.to_dict()), [0, 0, 1], atol=1e-9)
