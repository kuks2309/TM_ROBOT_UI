#!/usr/bin/env python3
import yaml
import numpy as np
from scipy.spatial.transform import Rotation


def create_transform_matrix(pose):
    x, y, z = pose['X'], pose['Y'], pose['Z']
    rx, ry, rz = pose['Rx'], pose['Ry'], pose['Rz']

    r = Rotation.from_euler('ZYX', [rz, ry, rx], degrees=True)
    R = r.as_matrix()

    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = [x, y, z]

    return T


def extract_pose(T):
    x, y, z = T[:3, 3]

    R = T[:3, :3]
    r = Rotation.from_matrix(R)
    rz, ry, rx = r.as_euler('ZYX', degrees=True)

    return {
        'X': round(float(x), 2),
        'Y': round(float(y), 2),
        'Z': round(float(z), 2),
        'Rx': round(float(rx), 2),
        'Ry': round(float(ry), 2),
        'Rz': round(float(rz), 2)
    }


def verify_runtime_file(runtime_file):
    print("=" * 70)
    print("변환 로직 검증")
    print("=" * 70)

    with open(runtime_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    tm_pose = data['reference']['tm_landmark']
    print(f"\n📍 TM Landmark 기준점:")
    print(f"   X={tm_pose['X']:.2f}, Y={tm_pose['Y']:.2f}, Z={tm_pose['Z']:.2f}")
    print(f"   Rx={tm_pose['Rx']:.2f}, Ry={tm_pose['Ry']:.2f}, Rz={tm_pose['Rz']:.2f}")

    T_tm = create_transform_matrix(tm_pose)

    print(f"\n{'Job':<5} {'Caption':<20} {'원본 일치':<10} {'오차 (mm/deg)'}")
    print("-" * 70)

    errors = []
    for job in data['jobs']:
        if job.get('coordinate_mode') != 'relative':
            continue

        if 'original_absolute' not in job:
            continue

        job_id = job['id']
        caption = job.get('caption', 'N/A')

        rel_pose = {
            'X': job['params']['X'],
            'Y': job['params']['Y'],
            'Z': job['params']['Z'],
            'Rx': job['params']['Rx'],
            'Ry': job['params']['Ry'],
            'Rz': job['params']['Rz']
        }

        orig_pose = job['original_absolute']

        T_rel = create_transform_matrix(rel_pose)
        T_abs_calc = T_tm @ T_rel
        calc_pose = extract_pose(T_abs_calc)

        def angle_diff(a1, a2):
            diff = abs(a1 - a2)
            while diff > 180:
                diff = abs(diff - 360)
            return diff

        err_x = abs(calc_pose['X'] - orig_pose['X'])
        err_y = abs(calc_pose['Y'] - orig_pose['Y'])
        err_z = abs(calc_pose['Z'] - orig_pose['Z'])
        err_rx = angle_diff(calc_pose['Rx'], orig_pose['Rx'])
        err_ry = angle_diff(calc_pose['Ry'], orig_pose['Ry'])
        err_rz = angle_diff(calc_pose['Rz'], orig_pose['Rz'])

        max_pos_err = max(err_x, err_y, err_z)
        max_rot_err = max(err_rx, err_ry, err_rz)

        tolerance_pos = 0.1
        tolerance_rot = 0.1

        if max_pos_err < tolerance_pos and max_rot_err < tolerance_rot:
            status = "✅ OK"
        else:
            status = "❌ FAIL"
            errors.append(job_id)

        print(f"{job_id:<5} {caption:<20} {status:<10} {max_pos_err:.3f}mm / {max_rot_err:.3f}°")

    print("=" * 70)

    if errors:
        print(f"\n❌ 검증 실패! {len(errors)}개 Job에서 오차 초과")
        return False
    else:
        print(f"\n✅ 검증 성공! 모든 Job이 허용 오차 내에 있습니다.")
        return True


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        runtime_file = sys.argv[1]
        verify_runtime_file(runtime_file)
    else:
        from pathlib import Path

        recipes_dir = Path("/home/amap/TM_Robot_ros2_ws/src/TM_Robot_Task_Manager/config/recipes")
        runtime_files = sorted(recipes_dir.glob("*_runtime.yaml"))

        if not runtime_files:
            print("❌ Runtime 파일을 찾을 수 없습니다")
            sys.exit(1)

        print(f"\n🔍 전수 검사: {len(runtime_files)}개 파일")
        print("=" * 70)

        all_passed = True
        for runtime_file in runtime_files:
            print(f"\n📁 {runtime_file.name}")
            success = verify_runtime_file(str(runtime_file))
            if not success:
                all_passed = False
            print()

        print("\n" + "=" * 70)
        if all_passed:
            print("✅ 전체 검증 성공! 모든 파일이 정상입니다.")
            sys.exit(0)
        else:
            print("❌ 일부 파일에서 오류가 발견되었습니다.")
            sys.exit(1)
