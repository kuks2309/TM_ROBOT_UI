#!/usr/bin/env python3
import argparse
import math
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tm_task_manager.tools.jig_plane_calculator import (
    JigPlaneCalculator,
    average_landmarks_from_files,
    plane_normal_from_pose,
    pose_in_plane_frame,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PLATE_DIR = PACKAGE_ROOT / 'data' / 'plate_pose_calc'
DEFAULT_OUT_DIR = PACKAGE_ROOT / 'data' / 'place_pose'
POSE_KEYS = ('x', 'y', 'z', 'rx', 'ry', 'rz')


def read_current_tcp(timeout_sec: float = 5.0) -> Optional[Dict[str, float]]:
    import rclpy
    from geometry_msgs.msg import PoseStamped
    from rclpy.node import Node

    received: List[Dict[str, float]] = []

    rclpy.init()
    node = Node('place_pose_recorder')
    try:
        def _on_pose(msg):
            if received:
                return
            p, o = msg.pose.position, msg.pose.orientation
            qx, qy, qz, qw = o.x, o.y, o.z, o.w

            sinr_cosp = 2 * (qw * qx + qy * qz)
            cosr_cosp = 1 - 2 * (qx * qx + qy * qy)
            rx = math.degrees(math.atan2(sinr_cosp, cosr_cosp))

            sinp = 2 * (qw * qy - qz * qx)
            ry = math.copysign(90.0, sinp) if abs(sinp) >= 1 else math.degrees(math.asin(sinp))

            siny_cosp = 2 * (qw * qz + qx * qy)
            cosy_cosp = 1 - 2 * (qy * qy + qz * qz)
            rz = math.degrees(math.atan2(siny_cosp, cosy_cosp))

            received.append({'x': p.x * 1000.0, 'y': p.y * 1000.0, 'z': p.z * 1000.0,
                             'rx': rx, 'ry': ry, 'rz': rz})

        node.create_subscription(PoseStamped, 'tool_pose', _on_pose, 10)
        deadline = time.time() + timeout_sec
        while not received and time.time() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
    finally:
        node.destroy_node()
        rclpy.shutdown()

    return received[0] if received else None


def build_reference(plate_dir: Path, prefix: str):
    files = sorted(f for f in plate_dir.glob(f"{prefix}*.yaml") if f.is_file())
    if not files:
        return None, [], []

    averaged, used, skipped = average_landmarks_from_files(files)
    if averaged is None:
        return None, used, skipped

    calc = JigPlaneCalculator()
    if not calc.load_from_dicts(averaged):
        return None, used, skipped
    return calc.to_dict(), used, skipped


def _fmt(pose: Dict[str, float]) -> str:
    return (f"X={pose['x']:9.3f} Y={pose['y']:9.3f} Z={pose['z']:9.3f}  "
            f"Rx={pose['rx']:8.3f} Ry={pose['ry']:8.3f} Rz={pose['rz']:8.3f}")


def print_summary(out_dir: Path, pallet: str) -> int:
    files = sorted(out_dir.glob(f"{pallet}_place_*.yaml"))
    if not files:
        print(f"기록 없음: {out_dir}/{pallet}_place_*.yaml")
        return 1

    rows = []
    for f in files:
        d = yaml.safe_load(f.read_text(encoding='utf-8')) or {}
        rel = d.get('relative_pose')
        if rel:
            rows.append((f.name, d.get('label', ''), rel))

    print(f"=== {pallet} place 기록 {len(rows)}건 (평면 좌표계) ===")
    print(f"{'파일':>28}{'라벨':>12}" + "".join(f"{k:>10}" for k in POSE_KEYS))
    for name, label, rel in rows:
        print(f"{name[-28:]:>28}{label[:10]:>12}" + "".join(f"{rel[k]:10.3f}" for k in POSE_KEYS))

    if len(rows) > 1:
        print("\n산포:")
        for k in POSE_KEYS:
            v = [r[2][k] for r in rows]
            mean = sum(v) / len(v)
            std = (sum((x - mean) ** 2 for x in v) / (len(v) - 1)) ** 0.5
            unit = 'mm' if k in ('x', 'y', 'z') else 'deg'
            print(f"  {k:>3}: 평균 {mean:9.3f}  std {std:7.3f}  "
                  f"PtP {max(v) - min(v):7.3f} {unit}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description='place 시점 TCP 를 평면 좌표계로 기록')
    ap.add_argument('--pallet', default='pallet0', help='기준 팔레트 접두어 (기본 pallet0)')
    ap.add_argument('--label', default='', help='기록에 붙일 메모 (예: 1층 좌상)')
    ap.add_argument('--plate-dir', default=str(DEFAULT_PLATE_DIR))
    ap.add_argument('--out-dir', default=str(DEFAULT_OUT_DIR))
    ap.add_argument('--summary', action='store_true', help='기록 통계만 출력')
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    if args.summary:
        return print_summary(out_dir, args.pallet)

    plate_pose, used, skipped = build_reference(Path(args.plate_dir), args.pallet)
    if plate_pose is None:
        print(f"[오류] 기준 plate_pose 를 만들 수 없습니다 ({args.plate_dir}/{args.pallet}*.yaml)")
        for path, reason in skipped:
            print(f"   건너뜀 {path.name}: {reason}")
        return 1

    tcp = read_current_tcp()
    if tcp is None:
        print("[오류] /tool_pose 를 받지 못했습니다 — 로봇 연결을 확인하세요")
        return 1

    relative = pose_in_plane_frame(plate_pose, tcp)
    normal = plane_normal_from_pose(plate_pose)
    saved_at = time.strftime('%Y-%m-%d %H:%M:%S')
    stamp = time.strftime('%Y%m%d_%H%M%S')

    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{args.pallet}_place_{stamp}.yaml"
    target.write_text(yaml.dump({
        'saved_at': saved_at,
        'pallet': args.pallet,
        'label': args.label,
        'reference': {
            'plate_pose': {k: round(plate_pose[k], 4) for k in POSE_KEYS},
            'plane_normal': [round(float(v), 6) for v in normal],
            'source_files': [Path(p).name for p in used],
            'source_count': len(used),
        },
        'tcp_pose_base': {k: round(tcp[k], 4) for k in POSE_KEYS},
        'relative_pose': {k: round(relative[k], 4) for k in POSE_KEYS},
    }, allow_unicode=True, sort_keys=False), encoding='utf-8')

    print(f"기준 plate_pose ({len(used)}개 평균)")
    print(f"   {_fmt(plate_pose)}")
    print(f"place 시점 TCP (로봇 베이스)")
    print(f"   {_fmt(tcp)}")
    print(f"평면 좌표계 상대 pose  ◀ 핵심")
    print(f"   {_fmt(relative)}")
    print(f"   x,y = 중심 기준 평면상 위치 / z = 법선 높이 / rz = 그리퍼 회전")
    print(f"저장: {target}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
