"""마커(Landmark) 좌표계 — 원점은 마커 위치, 회전은 프레임 모드로 고른다.

`rz_only` 는 마커의 Rz 만 쓰고 rx/ry 를 버린다. 마커 자세 측정 산포가
레버암에서 위치 오차로 증폭되기 때문이다 — 2026-08-15 드로어 마커 22회 실측에서
rx 범위 0.197°, ry 범위 0.129° 였고, 이는 250mm 레버암에서 각각 0.86mm, 0.56mm
위치 오차에 해당한다. 마크를 시야에 넣는 것처럼 평면 추종이 필요 없는 이동은
이 오차를 받을 이유가 없다.

`full` 은 마커 자세 전체를 쓴다. 박스를 옮기는 것처럼 공구가 대상 면을 따라가야
하는 이동에 쓴다.

평면(plate) 좌표계(`jig_plane_calculator.pose_from_plane_frame`)와는 원점·축 정의가
다르다 — 그쪽은 4 마크로 만든 평면이 기준이고, 이쪽은 마커 1 점이 기준이다.
회전·오일러 규약(ZYX)은 그 모듈과 같은 것을 쓴다.
"""
import math
from typing import Dict

import numpy as np

from .jig_plane_calculator import JigPlaneCalculator, _rotation_matrix_from_pose

POSE_KEYS = ('x', 'y', 'z', 'rx', 'ry', 'rz')

FRAME_MODE_RZ_ONLY = 'rz_only'
FRAME_MODE_FULL = 'full'
FRAME_MODES = (FRAME_MODE_RZ_ONLY, FRAME_MODE_FULL)


def landmark_frame_rotation(landmark: Dict[str, float],
                            frame_mode: str = FRAME_MODE_RZ_ONLY) -> np.ndarray:
    """마커 좌표계의 회전 행렬.

    rz_only: Z 축 회전만 (rx/ry 무시). full: 마커 자세 전체.
    """
    if frame_mode == FRAME_MODE_FULL:
        return _rotation_matrix_from_pose({
            'rx': float(landmark.get('rx', 0.0)),
            'ry': float(landmark.get('ry', 0.0)),
            'rz': float(landmark.get('rz', 0.0)),
        })

    if frame_mode != FRAME_MODE_RZ_ONLY:
        raise ValueError(f"알 수 없는 frame_mode: {frame_mode!r} (가능: {FRAME_MODES})")

    rz = math.radians(float(landmark.get('rz', 0.0)))
    c, s = math.cos(rz), math.sin(rz)
    return np.array([[c, -s, 0.0],
                     [s, c, 0.0],
                     [0.0, 0.0, 1.0]], dtype=float)


def _origin(landmark: Dict[str, float]) -> np.ndarray:
    return np.array([float(landmark['x']), float(landmark['y']), float(landmark['z'])],
                    dtype=float)


def pose_from_landmark_frame(landmark: Dict[str, float],
                             relative: Dict[str, float],
                             frame_mode: str = FRAME_MODE_RZ_ONLY) -> Dict[str, float]:
    """마커 좌표계 상대 pose 를 로봇 베이스 pose 로 되돌린다."""
    R = landmark_frame_rotation(landmark, frame_mode)
    rel_R = _rotation_matrix_from_pose({
        'rx': float(relative.get('rx', 0.0)),
        'ry': float(relative.get('ry', 0.0)),
        'rz': float(relative.get('rz', 0.0)),
    })
    offset = np.array([float(relative.get('x', 0.0)),
                       float(relative.get('y', 0.0)),
                       float(relative.get('z', 0.0))], dtype=float)

    position = _origin(landmark) + R @ offset
    rx, ry, rz = JigPlaneCalculator._rotation_matrix_to_euler_zyx(R @ rel_R)

    return {'x': float(position[0]), 'y': float(position[1]), 'z': float(position[2]),
            'rx': float(rx), 'ry': float(ry), 'rz': float(rz)}


def pose_in_landmark_frame(landmark: Dict[str, float],
                           pose: Dict[str, float],
                           frame_mode: str = FRAME_MODE_RZ_ONLY) -> Dict[str, float]:
    """pose_from_landmark_frame 의 역변환 — 현재 자세를 상대 오프셋으로 되돌린다.

    '현재위치 입력' 티칭이 이 방향을 쓴다. 절대 좌표가 상대 파라미터 칸에
    그대로 들어가는 사고를 구조적으로 막기 위해 역산해서 채운다.
    """
    R = landmark_frame_rotation(landmark, frame_mode)
    p = np.array([float(pose['x']), float(pose['y']), float(pose['z'])], dtype=float)

    offset = R.T @ (p - _origin(landmark))
    rel_R = R.T @ _rotation_matrix_from_pose({
        'rx': float(pose.get('rx', 0.0)),
        'ry': float(pose.get('ry', 0.0)),
        'rz': float(pose.get('rz', 0.0)),
    })
    rx, ry, rz = JigPlaneCalculator._rotation_matrix_to_euler_zyx(rel_R)

    return {'x': float(offset[0]), 'y': float(offset[1]), 'z': float(offset[2]),
            'rx': float(rx), 'ry': float(ry), 'rz': float(rz)}


TOOL_OFFSET_6DOF_KEYS = ('x', 'y', 'z', 'rx', 'ry', 'rz')


def apply_tool_offset_6dof(base_pose: Dict[str, float],
                           offset: Dict[str, float]) -> Dict[str, float]:
    """공구 좌표계 오차를 목표 pose 에 더한다 — z 축 포함.

    jig_plane_calculator.apply_tool_offset 은 z 를 뺀 5 축만 다룬다. 평면 수직
    정렬에서는 법선 방향 거리를 standoff_mm 이 이미 정하므로 z 손잡이가 둘이
    되는 것을 막기 위해서다. 마커 좌표계 이동에는 그런 손잡이가 없다 —
    offset_z 는 '목표를 어디에 둘지'이고 공구 z 오차는 '그리퍼가 얼마나 길게
    달렸는지'라 서로 다른 양이다. 그래서 여기서는 6 축을 모두 쓴다.
    """
    R = _rotation_matrix_from_pose(base_pose)
    offset_R = _rotation_matrix_from_pose({
        'rx': float(offset.get('rx', 0.0)),
        'ry': float(offset.get('ry', 0.0)),
        'rz': float(offset.get('rz', 0.0)),
    })
    translation = np.array([float(offset.get(k, 0.0)) for k in ('x', 'y', 'z')], dtype=float)

    origin = np.array([base_pose['x'], base_pose['y'], base_pose['z']], dtype=float)
    position = origin + R @ translation
    rx, ry, rz = JigPlaneCalculator._rotation_matrix_to_euler_zyx(R @ offset_R)

    return {'x': float(position[0]), 'y': float(position[1]), 'z': float(position[2]),
            'rx': float(rx), 'ry': float(ry), 'rz': float(rz)}


def tool_offset_6dof_from_poses(base_pose: Dict[str, float],
                                actual_pose: Dict[str, float]) -> Dict[str, float]:
    """apply_tool_offset_6dof 의 역변환 — 버리는 축이 없다."""
    R = _rotation_matrix_from_pose(base_pose)
    delta = np.array([float(actual_pose[k]) - float(base_pose[k]) for k in ('x', 'y', 'z')],
                     dtype=float)
    local = R.T @ delta
    rx, ry, rz = JigPlaneCalculator._rotation_matrix_to_euler_zyx(
        R.T @ _rotation_matrix_from_pose(actual_pose))

    return {'x': float(local[0]), 'y': float(local[1]), 'z': float(local[2]),
            'rx': float(rx), 'ry': float(ry), 'rz': float(rz)}
