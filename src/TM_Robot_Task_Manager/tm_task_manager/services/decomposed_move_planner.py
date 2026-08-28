from typing import List, Tuple

from .coordinate_transformer import CoordinateTransformer


DECOMPOSED_MIN_STEP_MM = 0.1
DECOMPOSED_MIN_STEP_DEG = 0.1


def build_decomposed_tcp_waypoints(current_pose: List[float],
                                   target: List[float]) -> Tuple[List[Tuple[str, List[float]]], str]:
    pose = list(current_pose[:6])
    target = list(target[:6])

    rotation_step = ('회전', (3, 4, 5))
    z_step = ('Z축', (2,))
    if abs(target[0] - pose[0]) >= abs(target[1] - pose[1]):
        long_step, short_step = ('X축', (0,)), ('Y축', (1,))
    else:
        long_step, short_step = ('Y축', (1,)), ('X축', (0,))

    if target[2] < pose[2] - DECOMPOSED_MIN_STEP_MM:
        order_label = '하강'
        sequence = [rotation_step, long_step, short_step, z_step]
    else:
        order_label = '상승/수평'
        sequence = [rotation_step, z_step, long_step, short_step]

    waypoints = []
    for label, indices in sequence:
        moved = any(
            CoordinateTransformer.angle_difference_deg(target[i], pose[i]) >= DECOMPOSED_MIN_STEP_DEG
            if i >= 3
            else abs(target[i] - pose[i]) >= DECOMPOSED_MIN_STEP_MM
            for i in indices
        )
        for i in indices:
            pose[i] = target[i]
        if moved:
            waypoints.append((label, list(pose)))

    if waypoints:
        waypoints[-1] = (waypoints[-1][0], list(target))

    return waypoints, order_label
