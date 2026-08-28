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
    R = _rotation_matrix_from_pose(base_pose)
    delta = np.array([float(actual_pose[k]) - float(base_pose[k]) for k in ('x', 'y', 'z')],
                     dtype=float)
    local = R.T @ delta
    rx, ry, rz = JigPlaneCalculator._rotation_matrix_to_euler_zyx(
        R.T @ _rotation_matrix_from_pose(actual_pose))

    return {'x': float(local[0]), 'y': float(local[1]), 'z': float(local[2]),
            'rx': float(rx), 'ry': float(ry), 'rz': float(rz)}
