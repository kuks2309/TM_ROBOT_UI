#!/usr/bin/env python3
"""지그 4점 마크의 평면 pose 계산과 평면/공구 좌표계 변환 유틸.

pose dict 는 x/y/z mm, rx/ry/rz deg — 로봇 베이스 좌표계, 오일러는 ZYX 합성.
CLI(main)로 positions.yaml 검산도 가능하다.
"""
import math
import argparse
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Tuple, Any
from pathlib import Path

import numpy as np
import yaml
from scipy.spatial.transform import Rotation


@dataclass
class Mark:
    """마크 한 점의 6축 측정값 (x/y/z mm, rx/ry/rz deg)."""
    x: float
    y: float
    z: float
    rx: float
    ry: float
    rz: float


@dataclass
class PlanePose:
    """계산된 평면 좌표계 pose — 원점=4점 중심, Z축=평면 법선 (mm/deg)."""
    x: float
    y: float
    z: float
    rx: float
    ry: float
    rz: float


class JigPlaneCalculator:
    """4점 마크에서 평면 pose 를 계산한다.

    마크 순서 계약: 1=좌하, 2=좌상, 3=우하, 4=우상 — 축 벡터를 인덱스 고정
    대각/변 벡터로 만들기 때문에 순서가 바뀌면 틀린 축으로도 성공 반환한다.
    """

    def __init__(self):
        self.marks: List[Mark] = []

    def load_from_yaml(self, yaml_path: str) -> bool:
        """positions.yaml 의 coordinate_definitions.jig_plate.scan_data 4점을 읽는다."""
        try:
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f)

            coord_defs = data.get('coordinate_definitions', {})
            jig_plate_data = coord_defs.get('jig_plate', {})
            scan_data = jig_plate_data.get('scan_data', [])

            self.marks = []
            for item in scan_data:
                landmark = item.get('landmark', {})
                self.marks.append(Mark(
                    x=landmark.get('x', 0),
                    y=landmark.get('y', 0),
                    z=landmark.get('z', 0),
                    rx=landmark.get('rx', 0),
                    ry=landmark.get('ry', 0),
                    rz=landmark.get('rz', 0)
                ))

            return len(self.marks) == 4

        except Exception as e:
            print(f"YAML 로드 오류: {e}")
            return False

    def load_from_marks(self, marks: List[Mark]) -> bool:
        if len(marks) != 4:
            print(f"4개의 mark가 필요합니다 (입력: {len(marks)}개)")
            return False
        self.marks = list(marks)
        return True

    def load_from_dicts(self, mark_dicts: List[Dict[str, float]]) -> bool:
        if len(mark_dicts) != 4:
            print(f"4개의 mark가 필요합니다 (입력: {len(mark_dicts)}개)")
            return False
        self.marks = [
            Mark(x=d['x'], y=d['y'], z=d['z'],
                 rx=d['rx'], ry=d['ry'], rz=d['rz'])
            for d in mark_dicts
        ]
        return True

    def calculate_plane_pose(self) -> Optional[PlanePose]:
        """4점에서 평면 pose 를 계산한다 (퇴화 배치는 None).

        중심은 산술 평균, X축은 좌→우 변 벡터 2개 평균, Y축은 하→상 변 벡터
        2개 평균, Z축은 그 외적 — 마크 자세(rx..rz)는 쓰지 않고 위치만 쓴다.
        """
        if len(self.marks) != 4:
            print(f"4개의 mark가 필요합니다 (현재: {len(self.marks)}개)")
            return None

        m = self.marks

        center_x = sum(mk.x for mk in m) / 4.0
        center_y = sum(mk.y for mk in m) / 4.0
        center_z = sum(mk.z for mk in m) / 4.0


        v_x1 = np.array([m[2].x - m[0].x, m[2].y - m[0].y, m[2].z - m[0].z])
        v_x2 = np.array([m[3].x - m[1].x, m[3].y - m[1].y, m[3].z - m[1].z])
        v_x = (v_x1 + v_x2) / 2.0

        v_y1 = np.array([m[1].x - m[0].x, m[1].y - m[0].y, m[1].z - m[0].z])
        v_y2 = np.array([m[3].x - m[2].x, m[3].y - m[2].y, m[3].z - m[2].z])
        v_y = (v_y1 + v_y2) / 2.0

        v_z = np.cross(v_x, v_y)

        x_norm = np.linalg.norm(v_x)
        y_norm = np.linalg.norm(v_y)
        z_norm = np.linalg.norm(v_z)

        if x_norm < 1e-10 or y_norm < 1e-10 or z_norm < 1e-10:
            print("벡터 크기가 0에 가깝습니다. mark 배치를 확인하세요.")
            return None

        axis_x = v_x / x_norm
        axis_z = v_z / z_norm

        axis_y = np.cross(axis_z, axis_x)
        axis_y = axis_y / np.linalg.norm(axis_y)

        R = np.column_stack([axis_x, axis_y, axis_z])

        rx, ry, rz = self._rotation_matrix_to_euler_zyx(R)

        return PlanePose(
            x=center_x, y=center_y, z=center_z,
            rx=rx, ry=ry, rz=rz
        )

    @staticmethod
    def _rotation_matrix_to_euler_zyx(R: np.ndarray) -> Tuple[float, float, float]:
        """회전행렬에서 ZYX 오일러 각(deg)을 추출한다 (짐벌락은 rx=0 고정 분기)."""
        sy = -R[2, 0]
        sy = np.clip(sy, -1.0, 1.0)
        ry = math.asin(float(sy))

        if abs(abs(sy) - 1.0) < 1e-6:
            rx = 0.0
            rz = math.atan2(-R[0, 1], R[1, 1])
        else:
            rx = math.atan2(R[2, 1], R[2, 2])
            rz = math.atan2(R[1, 0], R[0, 0])

        return (math.degrees(rx), math.degrees(ry), math.degrees(rz))

    def get_plane_info(self) -> Optional[str]:
        """입력 마크·계산 결과를 사람이 읽을 리포트 텍스트로 만든다."""
        result = self.calculate_plane_pose()
        if result is None:
            return None

        m = self.marks
        lines = []
        lines.append("=" * 55)
        lines.append("     Jig 평면 좌표 계산 결과")
        lines.append("=" * 55)
        lines.append("")

        lines.append("[입력 Mark 좌표]")
        layout_info = ["(좌하)", "(좌상)", "(우하)", "(우상)"]
        for i, mk in enumerate(m):
            lines.append(
                f"  Mark {i+1} {layout_info[i]}: "
                f"({mk.x:.2f}, {mk.y:.2f}, {mk.z:.2f}) "
                f"Rx={mk.rx:.2f}, Ry={mk.ry:.2f}, Rz={mk.rz:.2f}"
            )
        lines.append("")

        lines.append("[계산된 평면 자세]")
        lines.append(f"  X  = {result.x:.3f} mm")
        lines.append(f"  Y  = {result.y:.3f} mm")
        lines.append(f"  Z  = {result.z:.3f} mm")
        lines.append(f"  Rx = {result.rx:.3f} deg")
        lines.append(f"  Ry = {result.ry:.3f} deg")
        lines.append(f"  Rz = {result.rz:.3f} deg")
        lines.append("")

        avg_rx = sum(mk.rx for mk in m) / 4.0
        avg_ry = sum(mk.ry for mk in m) / 4.0
        avg_rz = sum(mk.rz for mk in m) / 4.0
        lines.append("[참고: Mark 자세 단순 평균]")
        lines.append(f"  Rx_avg = {avg_rx:.3f} deg")
        lines.append(f"  Ry_avg = {avg_ry:.3f} deg")
        lines.append(f"  Rz_avg = {avg_rz:.3f} deg")
        lines.append("")
        lines.append("=" * 55)

        return "\n".join(lines)

    def to_dict(self) -> Optional[Dict[str, float]]:
        result = self.calculate_plane_pose()
        if result is None:
            return None
        return {
            'x': result.x, 'y': result.y, 'z': result.z,
            'rx': result.rx, 'ry': result.ry, 'rz': result.rz
        }

    def calculate_distance_matrix(self) -> Optional[Dict[str, float]]:
        """4점 사이 6개 상호 거리(mm) — 배치 검산·직사각 검사용."""
        if len(self.marks) != 4:
            return None

        def dist(m1: Mark, m2: Mark) -> float:
            return math.sqrt((m2.x - m1.x)**2 + (m2.y - m1.y)**2 + (m2.z - m1.z)**2)

        m = self.marks
        return {
            'd_1_2': dist(m[0], m[1]),
            'd_1_3': dist(m[0], m[2]),
            'd_1_4': dist(m[0], m[3]),
            'd_2_3': dist(m[1], m[2]),
            'd_2_4': dist(m[1], m[3]),
            'd_3_4': dist(m[2], m[3])
        }

    def to_full_dict(self) -> Optional[Dict[str, Any]]:
        """평면 pose + 거리 행렬 + 계산 시각을 담은 저장용 dict."""
        pose = self.calculate_plane_pose()
        distances = self.calculate_distance_matrix()

        if pose is None:
            return None

        return {
            'plane_pose': {
                'x': round(pose.x, 3), 'y': round(pose.y, 3), 'z': round(pose.z, 3),
                'rx': round(pose.rx, 3), 'ry': round(pose.ry, 3), 'rz': round(pose.rz, 3)
            },
            'distance_matrix': {k: round(v, 3) for k, v in distances.items()} if distances else None,
            'calculated_at': datetime.now().isoformat()
        }


MIN_AXIS_NORM = 1e-9

MIN_KEEP_PROJECTION = 1e-6


def _rotation_matrix_from_pose(pose: Dict[str, float]) -> np.ndarray:
    """pose 의 rx/ry/rz(deg)로 ZYX 합성 회전행렬을 만든다 (scipy Rotation)."""
    return Rotation.from_euler(
        'ZYX',
        [pose['rz'], pose['ry'], pose['rx']],
        degrees=True,
    ).as_matrix()


def plane_normal_from_pose(pose: Dict[str, float]) -> np.ndarray:
    """평면 pose 의 단위 법선(Z축 열) — 퇴화 시 ValueError."""
    normal = _rotation_matrix_from_pose(pose)[:, 2]
    norm = np.linalg.norm(normal)
    if norm < MIN_AXIS_NORM:
        raise ValueError("법선 벡터 크기가 0 에 가깝습니다 — 평면 pose 를 확인하세요.")
    return normal / norm


def signed_point_to_plane_distance(
    point: Tuple[float, float, float],
    plane_pose: Dict[str, float],
) -> float:
    """점과 평면 사이 부호 거리(mm) — 법선 방향이 양수."""
    normal = plane_normal_from_pose(plane_pose)
    origin = np.array(
        [plane_pose['x'], plane_pose['y'], plane_pose['z']], dtype=float
    )
    return float(np.dot(np.asarray(point, dtype=float) - origin, normal))


def pose_in_plane_frame(
    plate_pose: Dict[str, float],
    tcp_pose: Dict[str, float],
) -> Dict[str, float]:
    """절대(베이스) pose 를 평면 좌표계 상대 pose 로 환산한다."""
    plane_rotation = _rotation_matrix_from_pose(plate_pose)
    tool_rotation = _rotation_matrix_from_pose(tcp_pose)

    origin = np.array(
        [plate_pose['x'], plate_pose['y'], plate_pose['z']], dtype=float
    )
    point = np.array([tcp_pose['x'], tcp_pose['y'], tcp_pose['z']], dtype=float)

    position = plane_rotation.T @ (point - origin)
    relative_rotation = plane_rotation.T @ tool_rotation
    rx, ry, rz = JigPlaneCalculator._rotation_matrix_to_euler_zyx(relative_rotation)

    return {
        'x': float(position[0]), 'y': float(position[1]), 'z': float(position[2]),
        'rx': rx, 'ry': ry, 'rz': rz,
    }


def pose_from_plane_frame(
    plate_pose: Dict[str, float],
    relative_pose: Dict[str, float],
) -> Dict[str, float]:
    """평면 좌표계 상대 pose 를 절대(베이스) pose 로 되돌린다."""
    plane_rotation = _rotation_matrix_from_pose(plate_pose)
    relative_rotation = _rotation_matrix_from_pose({
        'rx': float(relative_pose.get('rx', 0.0)),
        'ry': float(relative_pose.get('ry', 0.0)),
        'rz': float(relative_pose.get('rz', 0.0)),
    })

    origin = np.array(
        [plate_pose['x'], plate_pose['y'], plate_pose['z']], dtype=float
    )
    offset = np.array([
        float(relative_pose.get('x', 0.0)),
        float(relative_pose.get('y', 0.0)),
        float(relative_pose.get('z', 0.0)),
    ], dtype=float)

    position = origin + plane_rotation @ offset
    rx, ry, rz = JigPlaneCalculator._rotation_matrix_to_euler_zyx(
        plane_rotation @ relative_rotation
    )

    return {
        'x': float(position[0]), 'y': float(position[1]), 'z': float(position[2]),
        'rx': rx, 'ry': ry, 'rz': rz,
    }


def average_landmarks_from_files(
    file_paths: List[Any],
) -> Tuple[Optional[List[Dict[str, float]]], List[Any], List[Tuple[Any, str]]]:
    """측정 yaml 들의 jig1~4 마크를 단순 산술 평균한다 (outlier 제거 없음).

    Returns:
        (평균 마크 4개 또는 None, 사용 파일, (건너뛴 파일, 사유)).
    """
    keys = ('x', 'y', 'z', 'rx', 'ry', 'rz')
    sums = {i: {k: 0.0 for k in keys} for i in range(1, 5)}
    used: List[Any] = []
    skipped: List[Tuple[Any, str]] = []

    for path in file_paths:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            skipped.append((path, f"읽기 실패: {e}"))
            continue

        landmarks = data.get('landmarks') or {}
        if not all(f'jig{i}' in landmarks for i in range(1, 5)):
            skipped.append((path, "jig1~4 가 모두 있지 않음"))
            continue

        for i in range(1, 5):
            mark = landmarks[f'jig{i}']
            for k in keys:
                sums[i][k] += float(mark.get(k, 0.0))
        used.append(path)

    if not used:
        return None, used, skipped

    count = len(used)
    averaged = [
        dict({k: sums[i][k] / count for k in keys}, detected=True)
        for i in range(1, 5)
    ]
    return averaged, used, skipped


def tcp_pose_for_plane_normal(
    plane_pose: Dict[str, float],
    standoff_mm: float,
    rz_mode: str = 'keep',
    current_tcp: Optional[List[float]] = None,
) -> Dict[str, float]:
    """평면 법선 위 standoff_mm 지점에서 평면을 내려다보는 TCP 자세를 만든다.

    공구 Z축은 법선 반대(평면을 향함). rz_mode='keep' 은 현재 공구 X축을
    평면에 투영해 회전을 유지, 'plane' 은 평면 Y축(긴 변)에 정렬한다.

    Raises:
        ValueError: standoff 비양수, 모드 오류, keep 에 current_tcp 부재, 축 퇴화.
    """
    if standoff_mm <= 0:
        raise ValueError(f"standoff_mm 은 양수여야 합니다 (입력: {standoff_mm})")
    if rz_mode not in ('keep', 'plane'):
        raise ValueError(f"rz_mode 는 'keep' 또는 'plane' 이어야 합니다 (입력: {rz_mode})")

    plane_rotation = _rotation_matrix_from_pose(plane_pose)
    normal = plane_rotation[:, 2]
    normal = normal / np.linalg.norm(normal)

    axis_z = -normal

    axis_x = None
    if rz_mode == 'keep':
        if current_tcp is None or len(current_tcp) < 6:
            raise ValueError("rz_mode='keep' 에는 current_tcp [x,y,z,rx,ry,rz] 가 필요합니다")
        current_rotation = _rotation_matrix_from_pose({
            'rx': current_tcp[3], 'ry': current_tcp[4], 'rz': current_tcp[5]
        })
        projected = current_rotation[:, 0] - np.dot(current_rotation[:, 0], axis_z) * axis_z
        if np.linalg.norm(projected) >= MIN_KEEP_PROJECTION:
            axis_x = projected / np.linalg.norm(projected)

    if axis_x is None:
        source_axis = plane_rotation[:, 1] if rz_mode == 'plane' else plane_rotation[:, 0]
        axis_x = source_axis - np.dot(source_axis, axis_z) * axis_z
        norm_x = np.linalg.norm(axis_x)
        if norm_x < MIN_AXIS_NORM:
            axis_name = 'Y' if rz_mode == 'plane' else 'X'
            raise ValueError(
                f"평면 {axis_name}축이 법선과 평행합니다 — 평면 pose 를 확인하세요."
            )
        axis_x = axis_x / norm_x

    axis_y = np.cross(axis_z, axis_x)
    axis_y = axis_y / np.linalg.norm(axis_y)

    target_rotation = np.column_stack([axis_x, axis_y, axis_z])
    rx, ry, rz = JigPlaneCalculator._rotation_matrix_to_euler_zyx(target_rotation)

    center = np.array(
        [plane_pose['x'], plane_pose['y'], plane_pose['z']], dtype=float
    )
    position = center + normal * standoff_mm

    return {
        'x': float(position[0]), 'y': float(position[1]), 'z': float(position[2]),
        'rx': rx, 'ry': ry, 'rz': rz,
    }


TOOL_OFFSET_KEYS = ('x', 'y', 'rx', 'ry', 'rz')


def apply_tool_offset(
    base_pose: Dict[str, float],
    offset: Dict[str, float],
) -> Dict[str, float]:
    """공구 좌표계 5키 오프셋(TOOL_OFFSET_KEYS)을 합성한다 — 병진 z 는 0 고정.

    평면 정렬 보정 용도라 접근 높이(z)는 오프셋에 포함하지 않는다.
    z 까지 필요하면 landmark_frame.apply_tool_offset_6dof 를 쓴다.
    """
    base_rotation = _rotation_matrix_from_pose(base_pose)
    offset_rotation = _rotation_matrix_from_pose({
        'rx': float(offset.get('rx', 0.0)),
        'ry': float(offset.get('ry', 0.0)),
        'rz': float(offset.get('rz', 0.0)),
    })

    translation = np.array([
        float(offset.get('x', 0.0)),
        float(offset.get('y', 0.0)),
        0.0,
    ], dtype=float)

    origin = np.array(
        [base_pose['x'], base_pose['y'], base_pose['z']], dtype=float
    )
    position = origin + base_rotation @ translation
    rx, ry, rz = JigPlaneCalculator._rotation_matrix_to_euler_zyx(
        base_rotation @ offset_rotation
    )

    return {
        'x': float(position[0]), 'y': float(position[1]), 'z': float(position[2]),
        'rx': rx, 'ry': ry, 'rz': rz,
    }


def tool_offset_from_poses(
    base_pose: Dict[str, float],
    actual_pose: Dict[str, float],
) -> Tuple[Dict[str, float], float]:
    """두 pose 간 공구 좌표계 오프셋을 역산한다.

    Returns:
        (5키 오프셋 dict, 공구 z 방향 잔여 변위 dz mm) — dz 는 오프셋에서
        제외해 별도 보고한다.
    """
    base_rotation = _rotation_matrix_from_pose(base_pose)

    delta = np.array([
        float(actual_pose['x']) - float(base_pose['x']),
        float(actual_pose['y']) - float(base_pose['y']),
        float(actual_pose['z']) - float(base_pose['z']),
    ], dtype=float)
    local = base_rotation.T @ delta

    relative_rotation = base_rotation.T @ _rotation_matrix_from_pose(actual_pose)
    rx, ry, rz = JigPlaneCalculator._rotation_matrix_to_euler_zyx(relative_rotation)

    offset = {
        'x': float(local[0]), 'y': float(local[1]),
        'rx': rx, 'ry': ry, 'rz': rz,
    }
    return offset, float(local[2])


def main():
    """CLI: yaml 설정(기본 config/positions.yaml)의 4점으로 평면 리포트를 출력한다."""
    parser = argparse.ArgumentParser(description='Jig 4-Landmark 평면 좌표 계산기')
    parser.add_argument('--config', '-c', type=str, help='YAML 설정 파일 경로')
    args = parser.parse_args()

    calc = JigPlaneCalculator()

    if args.config:
        yaml_path = args.config
    else:
        yaml_path = str(Path(__file__).parent.parent.parent / "config" / "positions.yaml")

    if not Path(yaml_path).exists():
        print(f"파일을 찾을 수 없습니다: {yaml_path}")
        return

    if not calc.load_from_yaml(yaml_path):
        print("YAML 로드 실패 (4개 mark 필요)")
        return

    report = calc.get_plane_info()
    if report:
        print(report)


if __name__ == "__main__":
    main()
