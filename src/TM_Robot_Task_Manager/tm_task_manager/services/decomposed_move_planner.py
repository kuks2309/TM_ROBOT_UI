"""TCP 목표를 축 분해 경유점 열로 바꾸는 계획기 (mm/deg)."""
from typing import List, Tuple

from .coordinate_transformer import CoordinateTransformer


# 이 값 미만의 축 변화는 경유점을 만들지 않는다 (불필요한 미세 이동 방지)
DECOMPOSED_MIN_STEP_MM = 0.1
DECOMPOSED_MIN_STEP_DEG = 0.1


def build_decomposed_tcp_waypoints(current_pose: List[float],
                                   target: List[float]) -> Tuple[List[Tuple[str, List[float]]], str]:
    """현재→목표 TCP 이동을 축별 경유점 열로 분해한다.

    하강이면 회전→긴 수평축→짧은 수평축→Z 순 (Z 를 마지막에 내려 장애물
    위에서 XY 정렬을 끝내려는 의도), 상승/수평이면 회전→Z→수평 순.
    마지막 경유점은 누적 오차가 남지 않게 목표 원본으로 스냅한다.

    Returns:
        ([(축 라벨, pose[6])], 순서 라벨('하강'/'상승/수평')).
    """
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
