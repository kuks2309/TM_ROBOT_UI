import math
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import yaml

from ..tools.landmark_frame import FRAME_MODE_RZ_ONLY, pose_in_landmark_frame
from ..hardware.gripper import BACKENDS, SCHUNK, GripperBackend

CORNER_PLAN = ((4, 0.0, 0.0), (2, 1.0, 0.0), (1, 0.0, -1.0), (3, -1.0, 0.0))

MOUNT_FIXED = 'fixed'
MOUNT_FLOATING = 'floating'
MOUNTS = (MOUNT_FIXED, MOUNT_FLOATING)

NAME_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')

POSE_KEYS = ('x', 'y', 'z', 'rx', 'ry', 'rz')

APPROACH_LIFT_MM = 20.0
CLEAR_LIFT_MM = 250.0
TRAVEL_VELOCITY = 20.0
CONTACT_VELOCITY = 3.0
DECEL_ZONE_MM = 0.0
APPROACH_DECEL_VELOCITY = 10.0
CONTACT_DECEL_VELOCITY = 3.0
MAX_TILT_DEG = 30.0
MAX_RADIUS_MM = 200.0
GRIP_TIMEOUT_SEC = 15.0
GRIP_SETTLE_MS = 2000

DESCENT_PLANE_NORMAL = 'plane_normal'
DESCENT_TCP_LINEAR = 'tcp_linear'
DESCENT_MODES = (DESCENT_PLANE_NORMAL, DESCENT_TCP_LINEAR)

TCP_CONTACT_VELOCITY_MMS = 10.0
TCP_TRAVEL_VELOCITY_MMS = 50.0

MARKER_VIEW_LIFT_MM = 200.0

RADIUS_MARGIN_MM = 100.0

DEFAULT_SCAN_VELOCITY = 25.0


def _round_pose(pose: Dict[str, float], digits: int = 3) -> Dict[str, float]:
    return {key: round(float(pose.get(key, 0.0)), digits) for key in POSE_KEYS}


def _radius_3d(pose: Dict[str, float]) -> float:
    return math.sqrt(float(pose.get('x', 0.0)) ** 2
                     + float(pose.get('y', 0.0)) ** 2
                     + float(pose.get('z', 0.0)) ** 2)


def snap_rotation_to_plane(pose: Dict[str, float]) -> Dict[str, float]:
    snapped = dict(pose)
    snapped['rx'] = 180.0
    snapped['ry'] = 0.0
    snapped['rz'] = float(round(float(pose.get('rz', 0.0)) / 90.0) * 90.0)
    return snapped


class PalletRecipeGenerator:

    def __init__(self, recipe_dir: Optional[str] = None, package_root: Optional[str] = None,
                 gripper: Any = SCHUNK, descent: str = DESCENT_PLANE_NORMAL):
        if package_root is None:
            from .. import paths
            package_root = str(paths.PACKAGE_ROOT)
        self.package_root = package_root
        self.recipe_dir = recipe_dir or os.path.join(package_root, 'config', 'recipes')
        self.gripper: GripperBackend = (
            gripper if isinstance(gripper, GripperBackend)
            else BACKENDS[str(gripper).strip().lower()])
        mode = (descent or DESCENT_PLANE_NORMAL).strip().lower()
        if mode not in DESCENT_MODES:
            raise ValueError(
                '알 수 없는 하강 방식 %r — 가능한 값: %s'
                % (descent, ', '.join(DESCENT_MODES)))
        self.descent: str = mode


    def emit(self,
             pallet_name: str,
             mount: str,
             plate_pose: Dict[str, float],
             teach_poses: Dict[str, Dict[str, Dict[str, float]]],
             scan_start_tcp: Optional[Dict[str, float]] = None,
             marker_pose: Optional[Dict[str, float]] = None,
             marker_view_tcp: Optional[Dict[str, float]] = None,
             plate_marks: Optional[List[Dict[str, float]]] = None,
             pitch_x: float = 0.0,
             pitch_y: float = 0.0,
             trim_x: float = 0.0,
             trim_y: float = 0.0,
             operator: str = '',
             snap_rotation: bool = False,
             overwrite: bool = False) -> List[str]:
        self._validate(pallet_name, mount, plate_pose, teach_poses, marker_pose)

        snapshot = None
        if plate_marks:
            snapshot = self._write_plate_snapshot(
                pallet_name, plate_pose, plate_marks, operator)

        target_dir = os.path.join(self.recipe_dir, pallet_name)
        if mount == MOUNT_FIXED:
            documents = {
                f'{pallet_name}_pick.yaml': self._plane_motion(
                    pallet_name, teach_poses, 'pick', operator, snap_rotation),
                f'{pallet_name}_place.yaml': self._plane_motion(
                    pallet_name, teach_poses, 'place', operator, snap_rotation),
            }
            if scan_start_tcp:
                documents[f'{pallet_name}_cali.yaml'] = self._fixed_cali(
                    pallet_name, scan_start_tcp, pitch_x, pitch_y, trim_x, trim_y, operator)
        else:
            documents = {
                f'{pallet_name}_marker_scan.yaml': self._marker_scan(
                    pallet_name, marker_view_tcp, operator),
                f'{pallet_name}_pick.yaml': self._landmark_motion(
                    pallet_name, marker_pose, teach_poses, 'pick', operator,
                    snap_rotation),
                f'{pallet_name}_place.yaml': self._landmark_motion(
                    pallet_name, marker_pose, teach_poses, 'place', operator,
                    snap_rotation),
            }

        os.makedirs(target_dir, exist_ok=True)
        written: List[str] = []
        for filename, document in documents.items():
            path = os.path.join(target_dir, filename)
            if os.path.exists(path) and not overwrite:
                raise FileExistsError(f"이미 있습니다: {path}")
            with open(path, 'w', encoding='utf-8') as handle:
                yaml.safe_dump(document, handle, allow_unicode=True, sort_keys=False)
            written.append(path)
        if snapshot:
            written.append(snapshot)
        return written


    @staticmethod
    def _validate(pallet_name, mount, plate_pose, teach_poses, marker_pose) -> None:
        if not NAME_PATTERN.match(pallet_name or ''):
            raise ValueError(
                f"팔레트 이름이 올바르지 않습니다: '{pallet_name}' — "
                "영숫자로 시작하고 영숫자·밑줄·하이픈만 쓸 수 있습니다(최대 64자)"
            )
        if mount not in MOUNTS:
            raise ValueError(f"마운트는 {' 또는 '.join(MOUNTS)} 여야 합니다 (입력: {mount})")
        if not plate_pose or any(key not in plate_pose for key in POSE_KEYS):
            raise ValueError("평면 pose 가 없습니다 — 4점 측정을 먼저 수행하세요")
        for slot in ('pick', 'place'):
            entry = (teach_poses or {}).get(slot)
            if not entry or 'plane' not in entry or 'absolute' not in entry:
                raise ValueError(f"'{slot}' 티칭이 없습니다 — 조그로 자세를 잡고 저장하세요")
        if mount == MOUNT_FLOATING and not marker_pose:
            raise ValueError("비고정식은 위치 마커 측정이 필요합니다")


    @staticmethod
    def _header(name: str, summary: str, operator: str) -> Dict[str, Any]:
        today = datetime.now().strftime('%Y-%m-%d')
        return {
            'name': name,
            'description': summary,
            'version': '1.0',
            'created': today,
            'modified': today,
        }

    @staticmethod
    def _job(job_id: int, job_type: str, name: str, caption: str,
             params: Dict[str, Any]) -> Dict[str, Any]:
        job = {'id': job_id, 'type': job_type, 'name': name}
        if caption:
            job['caption'] = caption
        job['params'] = params
        return job

    @staticmethod
    def _renumber(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for index, job in enumerate(jobs, start=1):
            job['id'] = index
        return jobs

    def _recipe_info(self, job_id: int, description: str, operator: str) -> Dict[str, Any]:
        return self._job(job_id, 'recipe_info', 'Recipe 개요', '', {
            'mode': 'execution',
            'description': description,
            'author': operator or '',
            'version': '1.0',
            'vision_origin_check': 'none',
        })

    def _grip_job(self, job_id: int, closing: bool, caption: str = '') -> Dict[str, Any]:
        return self._job(job_id, self.gripper.job_type(closing),
                         self.gripper.job_name(closing), caption,
                         {'timeout': GRIP_TIMEOUT_SEC})

    def _settle_job(self, job_id: int) -> Dict[str, Any]:
        return self._job(job_id, 'wait', '대기', '그리퍼 동작 완료 대기',
                         {'duration': GRIP_SETTLE_MS})

    def _linear_job(self, job_id: int, caption: str, dz_mm: float,
                    velocity_mms: float) -> Dict[str, Any]:
        return self._job(job_id, 'move_linear', '직선 이동', caption, {
            'offset X': 0.0,
            'offset Y': 0.0,
            'offset Z': round(float(dz_mm), 3),
            'velocity': velocity_mms,
        })


    def _fixed_cali(self, pallet_name, scan_start_tcp, pitch_x, pitch_y,
                    trim_x, trim_y, operator) -> Dict[str, Any]:
        if not scan_start_tcp:
            raise ValueError("측정 시작 자세가 없습니다 — 4점 측정을 먼저 수행하세요")
        if pitch_x <= 0 or pitch_y <= 0:
            raise ValueError("마커 간격(가로·세로)이 필요합니다")

        start = _round_pose(scan_start_tcp)
        jobs: List[Dict[str, Any]] = [
            self._job(1, 'move_to_point', '포인트 이동', '1사분면 마커로 이동', {
                'motion_type': 'tcp',
                'X': start['x'], 'Y': start['y'], 'Z': start['z'],
                'Rx': start['rx'], 'Ry': start['ry'], 'Rz': start['rz'],
                'velocity': DEFAULT_SCAN_VELOCITY,
                'decomposed_tcp': True,
            }),
        ]

        job_id = 2
        for order, (jig_number, unit_x, unit_y) in enumerate(CORNER_PLAN, start=1):
            if order > 1:
                offset_x = unit_x * pitch_x
                offset_y = unit_y * pitch_y
                if order == len(CORNER_PLAN):
                    offset_x += trim_x
                    offset_y += trim_y
                jobs.append(self._job(job_id, 'move_linear', '직선 이동',
                                      f'{order}사분면 마커로 이동', {
                                          'offset X': round(offset_x, 3),
                                          'offset Y': round(offset_y, 3),
                                          'offset Z': 0.0,
                                          'velocity': 50.0,
                                      }))
                job_id += 1
            jobs.append(self._job(job_id, 'scan_tm_landmark_jig', 'TM Landmark Jig 스캔',
                                  f'{order}사분면_scan', {
                                      'jig_number': jig_number,
                                      'wait_after_command': 0,
                                      'repeat_count': 10,
                                      'outlier_method': '3sigma',
                                      'analysis_target': 'xyz',
                                  }))
            job_id += 1

        jobs.append(self._job(job_id, 'calculate_plate_pose', 'Plate Pose 계산',
                              f'{pallet_name}_plate_pose_calc', {
                                  'operator': operator or '',
                                  'save_path': f'data/plate_pose_calc/{pallet_name}',
                              }))

        document = self._header(
            f'{pallet_name}_cali',
            f'{pallet_name} 4점 측정 — 평면 pose 를 계산해 저장한다', operator)
        document['jobs'] = self._renumber(jobs)
        return document


    def _write_plate_snapshot(self, pallet_name, plate_pose, plate_marks,
                              operator) -> str:
        directory = os.path.join(self.package_root, 'data', 'plate_pose_calc', pallet_name)
        os.makedirs(directory, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        path = os.path.join(directory, f'{pallet_name}_teach_plate_pose_calc_{stamp}.yaml')

        landmarks = {}
        for mark in plate_marks:
            index = int(mark.get('jig_number', 0))
            if not 1 <= index <= 4:
                continue
            landmarks[f'jig{index}'] = {
                key: round(float(mark.get(key, 0.0)), 3) for key in POSE_KEYS
            }
        if len(landmarks) != 4:
            raise ValueError(
                f"평면 스냅샷에 jig1~4 가 모두 필요합니다 (받은 것: {sorted(landmarks)})")

        document = {
            'operator': operator or None,
            'recipe': f'{pallet_name}_teach',
            'task_caption': 'pallet_teach_tab',
            'saved_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'plate_pose': _round_pose(plate_pose),
            'landmarks': landmarks,
        }
        with open(path, 'w', encoding='utf-8') as handle:
            yaml.safe_dump(document, handle, allow_unicode=True, sort_keys=False)
        return path

    def _load_plate_job(self, job_id: int, pallet_name: str) -> Dict[str, Any]:
        return self._job(job_id, 'load_plate_pose', 'Plate Pose 불러오기',
                         f'{pallet_name} 저장 데이터 불러오기', {
                             'source_path': f'data/plate_pose_calc/{pallet_name}',
                             'file_prefix': f'{pallet_name}_teach',
                             'average_count': 1,
                             'rect_guard_enabled': True,
                             'max_side_diff_mm': 1.0,
                             'max_diagonal_diff_mm': 1.5,
                             'max_angle_error_deg': 1.0,
                         })

    def _plane_motion(self, pallet_name, teach_poses, slot, operator,
                      snap_rotation: bool = False) -> Dict[str, Any]:
        taught = _round_pose(teach_poses[slot]['plane'])
        if snap_rotation:
            taught = _round_pose(snap_rotation_to_plane(taught))
        near = dict(taught)
        near['z'] = round(taught['z'] + APPROACH_LIFT_MM, 3)
        clear = dict(taught)
        clear['z'] = round(taught['z'] + CLEAR_LIFT_MM, 3)

        picking = slot == 'pick'
        verb = '집' if picking else '놓'
        target_word = '집기' if picking else '놓기'
        leave_word = '들어올림' if picking else '빠짐'

        def plane_job(job_id, caption, pose, velocity, straight, decel):
            params = {
                'offset_x': pose['x'], 'offset_y': pose['y'], 'offset_z': pose['z'],
                'offset_rx': pose['rx'], 'offset_ry': pose['ry'], 'offset_rz': pose['rz'],
                'velocity': velocity,
            }
            if straight:
                params['straight_path'] = True
            params.update({
                'max_tilt_deg': MAX_TILT_DEG,
                'max_radius_mm': MAX_RADIUS_MM,
                'decel_zone_mm': DECEL_ZONE_MM,
                'decel_velocity': decel,
            })
            return self._job(job_id, 'move_to_plane_pose', '평면 좌표계 이동',
                             caption, params)

        jobs: List[Dict[str, Any]] = [
            self._recipe_info(1, f'{pallet_name} 에서 박스를 {verb}는다', operator),
        ]
        if picking:
            jobs.append(self._grip_job(2, closing=False, caption='집기 전 그리퍼 열기'))
            jobs.append(self._settle_job(3))

        step = len(jobs) + 1
        jobs.append(self._load_plate_job(step, pallet_name))
        jobs.append(plane_job(
            step + 1,
            f'상공 진입 ({target_word} 높이 +{CLEAR_LIFT_MM:.0f}mm)',
            clear, TRAVEL_VELOCITY, False, APPROACH_DECEL_VELOCITY))
        jobs.append(plane_job(
            step + 2,
            f'팔레트 위 접근 — 파지면 +{APPROACH_LIFT_MM:.0f}mm 위 (법선 하강)',
            near, TRAVEL_VELOCITY, True, APPROACH_DECEL_VELOCITY))
        if self.descent == DESCENT_TCP_LINEAR:
            jobs.append(self._linear_job(
                step + 3,
                f'팔레트{"에서" if picking else "에"} {target_word} (티칭값) — '
                f'공구축 직선 하강 {APPROACH_LIFT_MM:.0f}mm '
                f'@{TCP_CONTACT_VELOCITY_MMS:.0f}mm/s',
                APPROACH_LIFT_MM, TCP_CONTACT_VELOCITY_MMS))
            jobs.append(self._grip_job(step + 7, closing=picking))
            jobs.append(self._settle_job(step + 7))
            jobs.append(self._linear_job(
                step + 7,
                f'팔레트에서 {leave_word} — 공구축 직선 상승 '
                f'{APPROACH_LIFT_MM:.0f}mm @{TCP_CONTACT_VELOCITY_MMS:.0f}mm/s',
                -APPROACH_LIFT_MM, TCP_CONTACT_VELOCITY_MMS))
            jobs.append(self._linear_job(
                step + 6,
                f'팔레트에서 {leave_word} — 공구축 직선 상승 '
                f'{CLEAR_LIFT_MM - APPROACH_LIFT_MM:.0f}mm '
                f'@{TCP_TRAVEL_VELOCITY_MMS:.0f}mm/s',
                -(CLEAR_LIFT_MM - APPROACH_LIFT_MM), TCP_TRAVEL_VELOCITY_MMS))
        else:
            jobs.append(plane_job(
                step + 3,
                f'팔레트{"에서" if picking else "에"} {target_word} (티칭값) — '
                f'법선 직선 {APPROACH_LIFT_MM:.0f}mm @{CONTACT_VELOCITY:.0f}%',
                taught, CONTACT_VELOCITY, True, CONTACT_DECEL_VELOCITY))
            jobs.append(self._grip_job(step + 7, closing=picking))
            jobs.append(self._settle_job(step + 7))
            jobs.append(plane_job(
                step + 7,
                f'팔레트에서 {leave_word} ({target_word} 높이 +{CLEAR_LIFT_MM:.0f}mm) — '
                f'법선 직선 {APPROACH_LIFT_MM:.0f}mm @{CONTACT_VELOCITY:.0f}% (상승 정지 1회)',
                near, CONTACT_VELOCITY, True, CONTACT_DECEL_VELOCITY))
            jobs.append(plane_job(
                step + 6,
                f'팔레트에서 {leave_word} ({target_word} 높이 +{CLEAR_LIFT_MM:.0f}mm) — '
                f'법선 직선 {CLEAR_LIFT_MM - APPROACH_LIFT_MM:.0f}mm @{TRAVEL_VELOCITY:.0f}%',
                clear, TRAVEL_VELOCITY, True, CONTACT_DECEL_VELOCITY))

        document = self._header(
            f'{pallet_name} {target_word}',
            f'{pallet_name} 저장 평면({pallet_name}_teach)을 불러와 평면 좌표계로 '
            f'박스를 {verb}는다. 자세는 티칭 생값 그대로.', operator)
        document['jobs'] = self._renumber(jobs)
        return document


    def _marker_scan(self, pallet_name, marker_view_tcp, operator) -> Dict[str, Any]:
        if not marker_view_tcp:
            raise ValueError("마커 촬영 자세가 없습니다 — 위치 마커 촬영을 먼저 수행하세요")

        view = _round_pose(marker_view_tcp)

        def point_job(job_id, caption, z):
            return self._job(job_id, 'move_to_point', '포인트 이동', caption, {
                'motion_type': 'tcp',
                'X': view['x'], 'Y': view['y'], 'Z': round(z, 3),
                'Rx': view['rx'], 'Ry': view['ry'], 'Rz': view['rz'],
                'velocity': DEFAULT_SCAN_VELOCITY,
                'decomposed_tcp': True,
            })

        jobs = [
            self._grip_job(1, closing=True, caption='촬영 전 그리퍼 닫기 (카메라 시야 확보)'),
            self._job(2, 'wait', '대기', '그리퍼 안정화', {'duration': GRIP_SETTLE_MS}),
            point_job(3, f'촬영 자세 상공 {MARKER_VIEW_LIFT_MM:.0f}mm',
                      view['z'] + MARKER_VIEW_LIFT_MM),
            point_job(4, '위치 마커 촬영 자세 (하강)', view['z']),
            self._job(5, 'scan_tm_landmark', 'TM Landmark 스캔',
                      f'{pallet_name}_위치마커_스캔', {
                          'wait_after_command': 0,
                          'repeat_count': 10,
                          'outlier_method': '3sigma',
                          'analysis_target': 'xyz_rx_ry_rz',
                      }),
            self._job(6, 'save_landmark_pose', 'Landmark 좌표 저장',
                      f'{pallet_name}_위치마커_저장', {
                          'save_path': f'data/landmark_pose/{pallet_name}',
                          'operator': operator or '',
                      }),
        ]

        document = self._header(
            f'{pallet_name}_marker_scan',
            f'{pallet_name} 위치 마커 스캔 — 픽/플레이스 전에 실행한다 (비고정식)', operator)
        document['jobs'] = self._renumber(jobs)
        return document


    def _landmark_motion(self, pallet_name, marker_pose, teach_poses, slot,
                         operator, snap_rotation: bool = False) -> Dict[str, Any]:
        taught_absolute = teach_poses[slot]['absolute']
        taught = _round_pose(
            pose_in_landmark_frame(marker_pose, taught_absolute, FRAME_MODE_RZ_ONLY))
        if snap_rotation:
            taught = _round_pose(snap_rotation_to_plane(taught))

        near = dict(taught)
        near['z'] = round(taught['z'] + APPROACH_LIFT_MM, 3)
        clear = dict(taught)
        clear['z'] = round(taught['z'] + CLEAR_LIFT_MM, 3)

        radius = round(max(
            _radius_3d(pose) for pose in (taught, near, clear)
        ) + RADIUS_MARGIN_MM, 1)

        picking = slot == 'pick'
        verb = '집' if picking else '놓'
        target_word = '집기' if picking else '놓기'
        leave_word = '들어올림' if picking else '빠짐'

        def landmark_job(job_id, caption, pose, velocity, decel):
            return self._job(job_id, 'move_to_landmark_pose', '마커 좌표계 이동', caption, {
                'frame_mode': FRAME_MODE_RZ_ONLY,
                'offset_x': pose['x'], 'offset_y': pose['y'], 'offset_z': pose['z'],
                'offset_rx': pose['rx'], 'offset_ry': pose['ry'], 'offset_rz': pose['rz'],
                'landmark_source': 'file',
                'source_path': f'data/landmark_pose/{pallet_name}',
                'file_prefix': f'{pallet_name}_marker_scan',
                'average_count': 1,
                'max_age_min': 30.0,
                'tool_offset_x': 0.0, 'tool_offset_y': 0.0, 'tool_offset_z': 0.0,
                'tool_offset_rx': 0.0, 'tool_offset_ry': 0.0, 'tool_offset_rz': 0.0,
                'velocity': velocity,
                'max_radius_mm': radius,
                'decel_zone_mm': DECEL_ZONE_MM,
                'decel_velocity': decel,
            })

        jobs: List[Dict[str, Any]] = [
            self._recipe_info(1, f'{pallet_name} 에서 박스를 {verb}는다 (비고정식)', operator),
        ]
        if picking:
            jobs.append(self._grip_job(2, closing=False, caption='집기 전 그리퍼 열기'))
            jobs.append(self._settle_job(3))

        step = len(jobs) + 1
        jobs.append(landmark_job(
            step,
            f'상공 진입 (+{CLEAR_LIFT_MM:.0f}mm)',
            clear, TRAVEL_VELOCITY, APPROACH_DECEL_VELOCITY))
        jobs.append(landmark_job(
            step + 1,
            f'마커 기준 접근 — 파지면 +{APPROACH_LIFT_MM:.0f}mm 위',
            near, TRAVEL_VELOCITY, APPROACH_DECEL_VELOCITY))
        if self.descent == DESCENT_TCP_LINEAR:
            jobs.append(self._linear_job(
                step + 2,
                f'{target_word} (티칭값) — 공구축 직선 하강 {APPROACH_LIFT_MM:.0f}mm '
                f'@{TCP_CONTACT_VELOCITY_MMS:.0f}mm/s',
                APPROACH_LIFT_MM, TCP_CONTACT_VELOCITY_MMS))
            jobs.append(self._grip_job(step + 6, closing=picking))
            jobs.append(self._settle_job(step + 6))
            jobs.append(self._linear_job(
                step + 6,
                f'{leave_word} — 공구축 직선 상승 {APPROACH_LIFT_MM:.0f}mm '
                f'@{TCP_CONTACT_VELOCITY_MMS:.0f}mm/s',
                -APPROACH_LIFT_MM, TCP_CONTACT_VELOCITY_MMS))
            jobs.append(self._linear_job(
                step + 5,
                f'{leave_word} — 공구축 직선 상승 '
                f'{CLEAR_LIFT_MM - APPROACH_LIFT_MM:.0f}mm '
                f'@{TCP_TRAVEL_VELOCITY_MMS:.0f}mm/s',
                -(CLEAR_LIFT_MM - APPROACH_LIFT_MM), TCP_TRAVEL_VELOCITY_MMS))
        else:
            jobs.append(landmark_job(
                step + 2,
                f'{target_word} (티칭값) — 직선 {APPROACH_LIFT_MM:.0f}mm @{CONTACT_VELOCITY:.0f}%',
                taught, CONTACT_VELOCITY, CONTACT_DECEL_VELOCITY))
            jobs.append(self._grip_job(step + 6, closing=picking))
            jobs.append(self._settle_job(step + 6))
            jobs.append(landmark_job(
                step + 6,
                f'{leave_word} — 직선 {APPROACH_LIFT_MM:.0f}mm @{CONTACT_VELOCITY:.0f}%',
                near, CONTACT_VELOCITY, CONTACT_DECEL_VELOCITY))
            jobs.append(landmark_job(
                step + 5,
                f'{leave_word} — 직선 {CLEAR_LIFT_MM - APPROACH_LIFT_MM:.0f}mm '
                f'@{TRAVEL_VELOCITY:.0f}%',
                clear, TRAVEL_VELOCITY, CONTACT_DECEL_VELOCITY))

        document = self._header(
            f'{pallet_name} {target_word}',
            f'{pallet_name} 위치 마커 좌표계로 박스를 {verb}는다 (비고정식). '
            f'{pallet_name}_marker_scan 을 먼저 실행해야 한다', operator)
        document['jobs'] = self._renumber(jobs)
        return document
