#!/usr/bin/env python3
"""job_executor 평면 프레임 pick/place job 을 검증한다."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tm_task_manager.job_executor import JobExecutor
from tm_task_manager.tools.jig_plane_calculator import (
    pose_from_plane_frame,
    pose_in_plane_frame,
)

PLATE = {'x': 817.652, 'y': 215.032, 'z': -325.950,
         'rx': 0.261, 'ry': -0.074, 'rz': 89.574}
PLACE = {'x': 2.582, 'y': 1.524, 'z': 156.292,
         'rx': 179.673, 'ry': -0.058, 'rz': -90.008}


def test_round_trip_plane_frame():
    base = pose_from_plane_frame(PLATE, PLACE)
    back = pose_in_plane_frame(PLATE, base)
    for k in ('x', 'y', 'z'):
        assert back[k] == pytest.approx(PLACE[k], abs=1e-6)
    for k in ('rx', 'ry', 'rz'):
        assert back[k] == pytest.approx(PLACE[k], abs=1e-6)


def test_same_relative_pose_follows_the_plate():
    other = dict(PLATE, x=550.0, y=-220.0, rz=90.5)
    a = pose_from_plane_frame(PLATE, PLACE)
    b = pose_from_plane_frame(other, PLACE)
    assert a != b
    assert pose_in_plane_frame(other, b)['x'] == pytest.approx(PLACE['x'], abs=1e-6)
    assert pose_in_plane_frame(other, b)['rz'] == pytest.approx(PLACE['rz'], abs=1e-6)


class _Node:
    def __init__(self, tcp=None, base='RobotBase'):
        self.current_tcp_pose = tcp
        self.current_base_name = base
        self.motion_service = None


class _Ex:
    def __init__(self, tcp=None, base='RobotBase', plate=None, move_ok=True):
        self.ros_node = _Node(tcp, base)
        self.detected_plate_pose = plate
        self.saved_poses = {}
        self.logs = []
        self.moves = []
        self._move_ok = move_ok

    def _log(self, m):
        self.logs.append(m)

    def _move_to_position_line(self, motion_type, x, y, z, rx, ry, rz, vel):
        self.moves.append((x, y, z, rx, ry, rz, vel))
        return self._move_ok, f"이동 {'완료' if self._move_ok else '실패'}"

    def _log_orientation_deviation(self, *a, **k):
        pass

    _read_tcp_or_log = JobExecutor._read_tcp_or_log
    _move_pose_keep = JobExecutor._move_pose_keep
    _build_pose_keep_segments = JobExecutor._build_pose_keep_segments
    _build_descent_segments = JobExecutor._build_descent_segments
    _plane_normal_tilt_deg = JobExecutor._plane_normal_tilt_deg
    _exec_save_pose = JobExecutor._exec_save_pose
    _exec_move_to_saved_pose = JobExecutor._exec_move_to_saved_pose
    _exec_move_to_plane_pose = JobExecutor._exec_move_to_plane_pose


class _Job:
    def __init__(self, **p):
        self.params = p
        self.id = 1
        self.type = 't'


START = [700.0, 100.0, -200.0, 179.0, 0.5, -45.0]


def test_save_pose_stores_current_tcp():
    ex = _Ex(tcp=list(START))
    assert ex._exec_save_pose(_Job(key='start')) is True
    assert ex.saved_poses['start'] == START


def test_save_pose_fails_without_tcp():
    ex = _Ex(tcp=None)
    assert ex._exec_save_pose(_Job()) is False


def test_move_to_saved_pose_requires_prior_save():
    ex = _Ex(tcp=list(START))
    assert ex._exec_move_to_saved_pose(_Job(key='none')) is False
    assert any('저장된 자세가 없습니다' in m for m in ex.logs)


def test_move_to_saved_pose_returns_to_exact_pose():
    ex = _Ex(tcp=list(START))
    ex._exec_save_pose(_Job(key='start'))
    ex.ros_node.current_tcp_pose = [900.0, -50.0, -100.0, 170.0, 3.0, 10.0]
    assert ex._exec_move_to_saved_pose(_Job(key='start')) is True
    final = ex.moves[-1]
    assert final[0] == pytest.approx(START[0])
    assert final[1] == pytest.approx(START[1])
    assert final[2] == pytest.approx(START[2])
    assert final[3:6] == pytest.approx(START[3:6])


def test_plane_pose_requires_plate():
    ex = _Ex(tcp=list(START), plate=None)
    assert ex._exec_move_to_plane_pose(_Job(offset_z=150.0)) is False


def test_plane_pose_rejects_non_robotbase_frame():
    ex = _Ex(tcp=list(START), plate=PLATE, base='JigPlate')
    assert ex._exec_move_to_plane_pose(_Job(offset_z=150.0)) is False


def test_plane_pose_rejects_negative_height():
    ex = _Ex(tcp=list(START), plate=PLATE)
    assert ex._exec_move_to_plane_pose(_Job(offset_z=-10.0)) is False
    assert any('평면 아래로 이동 금지' in m for m in ex.logs)


def test_plane_pose_rejects_target_outside_pallet():
    ex = _Ex(tcp=list(START), plate=PLATE)
    assert ex._exec_move_to_plane_pose(
        _Job(offset_x=500.0, offset_z=150.0, max_radius_mm=200.0)) is False
    assert any('팔레트 밖으로' in m for m in ex.logs)


def test_plane_pose_moves_to_expected_base_target():
    ex = _Ex(tcp=list(START), plate=PLATE)
    assert ex._exec_move_to_plane_pose(_Job(
        offset_x=PLACE['x'], offset_y=PLACE['y'], offset_z=PLACE['z'],
        offset_rx=PLACE['rx'], offset_ry=PLACE['ry'], offset_rz=PLACE['rz'])) is True

    expected = pose_from_plane_frame(PLATE, PLACE)
    final = ex.moves[-1]
    assert final[0] == pytest.approx(expected['x'], abs=1e-6)
    assert final[1] == pytest.approx(expected['y'], abs=1e-6)
    assert final[2] == pytest.approx(expected['z'], abs=1e-6)
    assert final[3] == pytest.approx(expected['rx'], abs=1e-6)
    assert final[5] == pytest.approx(expected['rz'], abs=1e-6)


def test_plane_pose_aligns_orientation_before_approach():
    ex = _Ex(tcp=list(START), plate=PLATE)
    ex._exec_move_to_plane_pose(_Job(offset_z=150.0, offset_rz=-90.0))
    first = ex.moves[0]
    assert first[0] == pytest.approx(START[0])
    assert first[1] == pytest.approx(START[1])
    assert first[2] == pytest.approx(START[2])


def test_plane_pose_aborts_when_move_fails():
    ex = _Ex(tcp=list(START), plate=PLATE, move_ok=False)
    assert ex._exec_move_to_plane_pose(_Job(offset_z=150.0)) is False
    assert len(ex.moves) == 1
