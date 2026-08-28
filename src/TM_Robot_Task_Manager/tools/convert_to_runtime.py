#!/usr/bin/env python3
import sys
import yaml
import numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation
from typing import Dict, Any, Optional
import copy
from datetime import datetime


RUNTIME_ONLY_JOBS = {
    'find_landmark': {
        'insert_before': 'scan_tm_landmark',
        'name': 'Landmark 검색',
        'caption': 'Landmark 검색',
        'default_params': {
            'grid_step': 30.0,
            'grid_size': 3,
            'scan_timeout': 500,
            'velocity': 30.0,
            'on_found': 'store_position',
            'on_not_found': 'abort'
        }
    }
}


class RecipeConverter:
    def __init__(self, jig_plate_file: Optional[str] = None,
                 runtime_job_config: Optional[str] = None,
                 landmark_pose_file: Optional[str] = None):
        self.jig_plate_file = jig_plate_file
        self.runtime_job_config = runtime_job_config
        self.landmark_pose_file = landmark_pose_file

    def create_transform_matrix(self, pose: Dict[str, float]) -> np.ndarray:
        x, y, z = pose['X'], pose['Y'], pose['Z']
        rx, ry, rz = pose['Rx'], pose['Ry'], pose['Rz']

        r = Rotation.from_euler('ZYX', [rz, ry, rx], degrees=True)
        R = r.as_matrix()

        T = np.eye(4)
        T[:3, :3] = R
        T[:3, 3] = [x, y, z]

        return T

    def extract_pose(self, T: np.ndarray) -> Dict[str, float]:
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

    def load_jig_plate_calibration(self) -> Optional[Dict[str, float]]:
        if not self.jig_plate_file:
            return None

        try:
            with open(self.jig_plate_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            jig_landmark = data.get('coordinate_definitions', {}).get('jig_landmark', {})
            tool_pose = jig_landmark.get('tool_pose', {})

            if not all(k in tool_pose for k in ['x', 'y', 'z', 'rx', 'ry', 'rz']):
                print(f"⚠️  Jig Plate 파일에 jig_landmark.tool_pose 정보가 불완전합니다")
                return None

            pose = {
                'X': tool_pose['x'],
                'Y': tool_pose['y'],
                'Z': tool_pose['z'],
                'Rx': tool_pose['rx'],
                'Ry': tool_pose['ry'],
                'Rz': tool_pose['rz']
            }

            print(f"✅ Jig Plate Calibration 파일 로드: {self.jig_plate_file}")
            print(f"✅ jig_landmark 좌표: X={pose['X']}, Y={pose['Y']}, Z={pose['Z']}, "
                  f"Rx={pose['Rx']}, Ry={pose['Ry']}, Rz={pose['Rz']}")

            return pose

        except Exception as e:
            print(f"⚠️  Jig Plate 파일 읽기 실패: {e}")
            return None

    def load_landmark_pose(self) -> Optional[Dict[str, float]]:
        """save_landmark_pose Job 이 남긴 파일에서 기준 Landmark 좌표를 읽는다.

        마스터의 reference.tm_jig_landmark 가 없을 때 쓰는 기준점 소스다.
        그 블록은 GUI 저장 시에만 갱신되고 스캔이 비면 옛 값으로 조용히
        폴백하는 반면, 이 파일은 레시피 실행 중 스캔 직후에 기록되므로
        측정과 기준점이 같은 실행에서 나온 것임이 보장된다.
        """
        if not self.landmark_pose_file:
            return None

        try:
            with open(self.landmark_pose_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            landmark = (data or {}).get('landmark', {})

            if not all(k in landmark for k in ['x', 'y', 'z', 'rx', 'ry', 'rz']):
                print(f"⚠️  Landmark Pose 파일에 landmark 좌표가 불완전합니다: {self.landmark_pose_file}")
                return None

            pose = {
                'X': landmark['x'],
                'Y': landmark['y'],
                'Z': landmark['z'],
                'Rx': landmark['rx'],
                'Ry': landmark['ry'],
                'Rz': landmark['rz']
            }

            print(f"✅ Landmark Pose 파일 로드: {self.landmark_pose_file}")
            print(f"✅ 기준 Landmark 좌표: X={pose['X']}, Y={pose['Y']}, Z={pose['Z']}, "
                  f"Rx={pose['Rx']}, Ry={pose['Ry']}, Rz={pose['Rz']}")

            return pose

        except Exception as e:
            print(f"⚠️  Landmark Pose 파일 읽기 실패: {e}")
            return None

    def _load_runtime_job_params(self, job_type: str) -> Dict[str, Any]:
        defaults = RUNTIME_ONLY_JOBS[job_type]['default_params'].copy()

        if self.runtime_job_config:
            try:
                with open(self.runtime_job_config, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                if config and job_type in config:
                    defaults.update(config[job_type])
                    print(f"  설정 파일에서 {job_type} 파라미터 로드 완료")
            except Exception as e:
                print(f"  설정 파일 로드 실패 ({e}), 기본값 사용")

        return defaults

    def _insert_runtime_only_jobs(self, jobs: list) -> list:
        result = list(jobs)

        existing_types = {job.get('type') for job in result}

        insertions = {}
        for job_type, config in RUNTIME_ONLY_JOBS.items():
            if job_type in existing_types:
                print(f"  {job_type}: 마스터에 이미 존재 → 삽입 건너뜀")
                continue
            target = config['insert_before']
            if target not in insertions:
                insertions[target] = []
            job_dict = {
                'type': job_type,
                'name': config['name'],
                'caption': config.get('caption', config['name']),
                'params': self._load_runtime_job_params(job_type)
            }
            insertions[target].append(job_dict)

        insert_points = []
        for i, job in enumerate(result):
            jtype = job.get('type')
            if jtype in insertions:
                insert_points.append((i, insertions[jtype]))

        for idx, jobs_to_insert in reversed(insert_points):
            for job_dict in reversed(jobs_to_insert):
                result.insert(idx, job_dict)
                print(f"  Runtime-only job 삽입: {job_dict['type']} (위치: {idx + 1})")

        for i, job in enumerate(result):
            job['id'] = i + 1

        return result

    def convert_to_relative(self, master_file: str, output_file: str) -> bool:
        print(f"📖 마스터 파일 읽기: {master_file}")
        try:
            with open(master_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except Exception as e:
            print(f"❌ 파일 읽기 실패: {e}")
            return False

        print(f"\n🔧 Runtime 전용 job 삽입 중...")
        data['jobs'] = self._insert_runtime_only_jobs(data['jobs'])
        print(f"  총 {len(data['jobs'])}개 job (삽입 후)")

        scan_job_index = None
        for i, job in enumerate(data['jobs']):
            if job.get('type') == 'scan_tm_landmark':
                scan_job_index = i
                print(f"✅ scan_tm_landmark 발견: Job {job['id']} (index {i})")
                break

        if scan_job_index is None:
            print(f"❌ scan_tm_landmark Job을 찾을 수 없습니다")
            return False

        tm_pose = None

        master_ref = data.get('reference', {}).get('tm_jig_landmark')
        if master_ref and isinstance(master_ref, dict) and all(k in master_ref for k in ['X', 'Y', 'Z', 'Rx', 'Ry', 'Rz']):
            tm_pose = master_ref
            print(f"✅ 마스터 reference.tm_jig_landmark 사용: "
                  f"X={tm_pose['X']}, Y={tm_pose['Y']}, Z={tm_pose['Z']}, "
                  f"Rx={tm_pose['Rx']}, Ry={tm_pose['Ry']}, Rz={tm_pose['Rz']}")

        if tm_pose is None:
            tm_pose = self.load_landmark_pose()
            if tm_pose:
                print(f"⚠️  마스터 reference 없음 - save_landmark_pose 산출물에서 기준점 로드")

        if tm_pose is None:
            tm_pose = self.load_jig_plate_calibration()
            if tm_pose:
                print(f"⚠️  마스터 reference 없음 - Jig Plate Calibration 파일에서 기준점 로드")

        if tm_pose is None:
            print(f"❌ TM Landmark 기준점을 찾을 수 없습니다")
            print(f"❌ 다음 중 하나가 필요합니다:")
            print(f"❌   - 마스터 파일의 reference.tm_jig_landmark")
            print(f"❌   - save_landmark_pose Job 이 남긴 data/landmark_pose/*.yaml")
            print(f"❌   - Jig Plate Calibration 파일 (data/jig_mark/**/*.yaml)")
            return False

        print(f"✅ TM Landmark 기준점: X={tm_pose['X']}, Y={tm_pose['Y']}, Z={tm_pose['Z']}, "
              f"Rx={tm_pose['Rx']}, Ry={tm_pose['Ry']}, Rz={tm_pose['Rz']}")

        T_tm = self.create_transform_matrix(tm_pose)
        T_tm_inv = np.linalg.inv(T_tm)

        recipe_mode = 'execution'
        for job in data['jobs']:
            if job.get('type') == 'recipe_info':
                recipe_mode = job.get('params', {}).get('mode', 'execution')
                break
        print(f"📋 Recipe 모드: {recipe_mode}")
        if recipe_mode == 'teaching':
            print(f"  → Teaching 모드: TCP 자세(Rx,Ry,Rz)는 마스터 값 유지, X,Y,Z만 상대좌표 변환")

        runtime_data = copy.deepcopy(data)
        runtime_data['name'] = f"{data['name']} (Runtime)"
        runtime_data['description'] = 'TM Landmark 기준 상대좌표 실행 파일'
        runtime_data['master_file'] = Path(master_file).name
        runtime_data['master_modified'] = data.get('modified', '')
        runtime_data['modified'] = datetime.now().strftime("%Y-%m-%d")
        runtime_data['reference'] = {
            'tm_jig_landmark': {
                'X': tm_pose['X'],
                'Y': tm_pose['Y'],
                'Z': tm_pose['Z'],
                'Rx': tm_pose['Rx'],
                'Ry': tm_pose['Ry'],
                'Rz': tm_pose['Rz']
            }
        }

        converted_count = 0
        scan_job_id = data['jobs'][scan_job_index]['id']

        for i, job in enumerate(runtime_data['jobs']):
            job_id = job['id']

            if i <= scan_job_index:
                job['coordinate_mode'] = 'absolute'
                params = job.get('params', {})
                if all(k in params for k in ['X', 'Y', 'Z', 'Rx', 'Ry', 'Rz']):
                    job['robot_base'] = {k: params[k] for k in ['X', 'Y', 'Z', 'Rx', 'Ry', 'Rz']}
                continue

            if 'params' not in job:
                job['coordinate_mode'] = 'none'
                continue

            params = job['params']
            if not all(k in params for k in ['X', 'Y', 'Z']):
                job['coordinate_mode'] = 'none'
                continue

            if 'Rx' not in params:
                params['Rx'] = 0.0
            if 'Ry' not in params:
                params['Ry'] = 0.0
            if 'Rz' not in params:
                params['Rz'] = 0.0

            abs_pose = {
                'X': params['X'],
                'Y': params['Y'],
                'Z': params['Z'],
                'Rx': params['Rx'],
                'Ry': params['Ry'],
                'Rz': params['Rz']
            }
            T_abs = self.create_transform_matrix(abs_pose)

            T_rel = T_tm_inv @ T_abs

            rel_pose = self.extract_pose(T_rel)

            job['original_absolute'] = abs_pose.copy()
            job['robot_base'] = abs_pose.copy()

            job['coordinate_mode'] = 'relative'
            params['X'] = rel_pose['X']
            params['Y'] = rel_pose['Y']
            params['Z'] = rel_pose['Z']

            if recipe_mode == 'teaching':
                params['Rx'] = abs_pose['Rx']
                params['Ry'] = abs_pose['Ry']
                params['Rz'] = abs_pose['Rz']
            else:
                params['Rx'] = rel_pose['Rx']
                params['Ry'] = rel_pose['Ry']
                params['Rz'] = rel_pose['Rz']

            T_verify = T_tm @ T_rel
            verify_pose = self.extract_pose(T_verify)
            err_x = abs(verify_pose['X'] - abs_pose['X'])
            err_y = abs(verify_pose['Y'] - abs_pose['Y'])
            err_z = abs(verify_pose['Z'] - abs_pose['Z'])
            max_err = max(err_x, err_y, err_z)

            if max_err > 0.1:
                print(f"  ❌ Job {job_id:2d}: {job.get('caption', 'N/A'):20s} 역변환 오차 {max_err:.3f}mm (X={err_x:.3f} Y={err_y:.3f} Z={err_z:.3f})")
                return False
            else:
                print(f"  Job {job_id:2d}: {job.get('caption', 'N/A'):20s} → 상대좌표 변환 OK (역변환 오차 {max_err:.3f}mm)")

            converted_count += 1

        print(f"\n💾 Runtime 파일 저장: {output_file}")
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"# Recipe: {runtime_data['name']}\n")
                f.write(f"# TM Task Manager Recipe File\n")
                f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Master: {Path(master_file).name}\n\n")
                yaml.dump(runtime_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        except Exception as e:
            print(f"❌ 파일 저장 실패: {e}")
            return False

        print(f"✅ 변환 완료: {converted_count}개 Job 상대좌표로 변환")
        return True


def find_latest_jig_plate_file() -> Optional[str]:
    jig_mark_dir = Path(__file__).parent.parent / "data" / "jig_mark"

    if not jig_mark_dir.exists():
        return None

    yaml_files = list(jig_mark_dir.glob("**/*.yaml"))

    if not yaml_files:
        return None

    latest_file = max(yaml_files, key=lambda f: f.stat().st_mtime)
    return str(latest_file)


def find_latest_landmark_pose_file() -> Optional[str]:
    """save_landmark_pose 산출물 중 가장 최근 것 (mtime 기준).

    find_latest_jig_plate_file 과 같은 규약 — 폴더가 없거나 비면 None.
    """
    landmark_dir = Path(__file__).parent.parent / "data" / "landmark_pose"

    if not landmark_dir.exists():
        return None

    yaml_files = list(landmark_dir.glob("**/*.yaml"))

    if not yaml_files:
        return None

    latest_file = max(yaml_files, key=lambda f: f.stat().st_mtime)
    return str(latest_file)


def find_latest_runtime_job_config() -> Optional[str]:
    config_dir = Path(__file__).parent.parent / "config"
    config_file = config_dir / "runtime_job_defaults.yaml"

    if config_file.exists():
        return str(config_file)
    return None


def main():
    if len(sys.argv) > 1:
        master_file = sys.argv[1]
    else:
        master_file = "/home/amap/TM_Robot_ros2_ws/src/TM_Robot_Task_Manager/config/recipes/tm_landmark_test4.yaml"

    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        master_path = Path(master_file)
        output_file = str(master_path.parent / f"{master_path.stem}_runtime{master_path.suffix}")

    if len(sys.argv) > 3:
        jig_plate_file = sys.argv[3]
    else:
        jig_plate_file = find_latest_jig_plate_file()

    runtime_job_config = find_latest_runtime_job_config()
    landmark_pose_file = find_latest_landmark_pose_file()

    print("=" * 70)
    print("Recipe 변환: 마스터 → Runtime")
    print("=" * 70)
    print(f"입력: {master_file}")
    print(f"출력: {output_file}")
    if landmark_pose_file:
        print(f"Landmark Pose: {landmark_pose_file}")
    if jig_plate_file:
        print(f"Jig Plate: {jig_plate_file}")
    if runtime_job_config:
        print(f"Runtime Job 설정: {runtime_job_config}")
    print("=" * 70)

    converter = RecipeConverter(
        jig_plate_file=jig_plate_file,
        runtime_job_config=runtime_job_config,
        landmark_pose_file=landmark_pose_file
    )
    success = converter.convert_to_relative(master_file, output_file)

    if success:
        print("\n" + "=" * 70)
        print("✅ 변환 성공!")
        print("=" * 70)
        return 0
    else:
        print("\n" + "=" * 70)
        print("❌ 변환 실패!")
        print("=" * 70)
        return 1


if __name__ == '__main__':
    sys.exit(main())
