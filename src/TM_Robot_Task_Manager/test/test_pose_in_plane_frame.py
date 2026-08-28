#!/usr/bin/env python3
"""pose_in_plane_frame / average_landmarks_from_files 단위 테스트."""
import math
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tm_task_manager.tools.jig_plane_calculator import (
    average_landmarks_from_files,
    pose_in_plane_frame,
    tcp_pose_for_plane_normal,
)

FLAT = {'x': 100.0, 'y': 200.0, 'z': -300.0, 'rx': 0.0, 'ry': 0.0, 'rz': 0.0}


def test_identity_when_tcp_equals_plate():
    rel = pose_in_plane_frame(FLAT, dict(FLAT))
    for k in ('x', 'y', 'z', 'rx', 'ry', 'rz'):
        assert rel[k] == pytest.approx(0.0, abs=1e-9)


def test_pure_translation_maps_to_plane_axes():
    tcp = dict(FLAT, x=110.0, y=205.0, z=-280.0)
    rel = pose_in_plane_frame(FLAT, tcp)
    assert rel['x'] == pytest.approx(10.0)
    assert rel['y'] == pytest.approx(5.0)
    assert rel['z'] == pytest.approx(20.0)


def test_plate_rotation_is_removed():
    """평면이 Rz=90도 돌아 있으면 베이스 +X 변위는 평면 -Y 로 나온다."""
    plate = dict(FLAT, rz=90.0)
    tcp = dict(FLAT, x=110.0, rz=90.0)
    rel = pose_in_plane_frame(plate, tcp)
    assert rel['x'] == pytest.approx(0.0, abs=1e-9)
    assert rel['y'] == pytest.approx(-10.0)
    assert rel['rz'] == pytest.approx(0.0, abs=1e-9)


def test_gripper_rotation_error_is_reported_as_rz():
    tcp = dict(FLAT, rz=7.5)
    rel = pose_in_plane_frame(FLAT, tcp)
    assert rel['rz'] == pytest.approx(7.5)
    assert rel['rx'] == pytest.approx(0.0, abs=1e-9)


def test_z_matches_standoff_from_align_helper():
    """align 이 만든 목표 pose 를 되돌리면 평면 좌표계에서 (0,0,standoff) 여야 한다."""
    plate = {'x': 817.6, 'y': 215.0, 'z': -325.9,
             'rx': 0.26, 'ry': -0.07, 'rz': 89.58}
    target = tcp_pose_for_plane_normal(plate, 150.0, 'plane', None)
    rel = pose_in_plane_frame(plate, target)
    assert rel['x'] == pytest.approx(0.0, abs=1e-6)
    assert rel['y'] == pytest.approx(0.0, abs=1e-6)
    assert rel['z'] == pytest.approx(150.0, abs=1e-6)


def test_tilted_plate_z_is_normal_distance():
    """기울어진 평면에서도 z 는 법선 방향 거리다."""
    plate = dict(FLAT, ry=30.0)
    # 법선 방향으로 50mm 떨어진 점
    n = (math.sin(math.radians(30.0)), 0.0, math.cos(math.radians(30.0)))
    tcp = dict(FLAT, x=FLAT['x'] + 50 * n[0], z=FLAT['z'] + 50 * n[2], ry=30.0)
    rel = pose_in_plane_frame(plate, tcp)
    assert rel['z'] == pytest.approx(50.0, abs=1e-6)
    assert rel['x'] == pytest.approx(0.0, abs=1e-6)


# ---- average_landmarks_from_files ----

def _write(path, jig1_y, ok=True):
    lm = {f'jig{i}': {'x': 10.0 * i, 'y': jig1_y + i, 'z': -5.0,
                      'rx': 180.0, 'ry': 0.0, 'rz': 90.0} for i in range(1, 5)}
    if not ok:
        del lm['jig3']
    path.write_text(yaml.dump({'landmarks': lm}), encoding='utf-8')
    return path


def test_average_of_two_files(tmp_path):
    a = _write(tmp_path / 'a.yaml', 0.0)
    b = _write(tmp_path / 'b.yaml', 10.0)
    marks, used, skipped = average_landmarks_from_files([a, b])
    assert len(used) == 2 and not skipped
    assert marks[0]['y'] == pytest.approx(6.0)   # (1 + 11) / 2
    assert marks[0]['detected'] is True


def test_incomplete_file_is_skipped(tmp_path):
    a = _write(tmp_path / 'a.yaml', 0.0)
    b = _write(tmp_path / 'b.yaml', 99.0, ok=False)
    marks, used, skipped = average_landmarks_from_files([a, b])
    assert used == [a]
    assert len(skipped) == 1 and 'jig1~4' in skipped[0][1]
    assert marks[0]['y'] == pytest.approx(1.0)


def test_all_invalid_returns_none(tmp_path):
    b = _write(tmp_path / 'b.yaml', 0.0, ok=False)
    marks, used, skipped = average_landmarks_from_files([b])
    assert marks is None and used == [] and len(skipped) == 1


def test_unreadable_file_is_skipped(tmp_path):
    marks, used, skipped = average_landmarks_from_files([tmp_path / 'nope.yaml'])
    assert marks is None
    assert '읽기 실패' in skipped[0][1]
