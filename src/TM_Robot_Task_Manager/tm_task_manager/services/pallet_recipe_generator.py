"""팔레트 픽앤플레이스 레시피 발행기.

티칭 마법사가 측정한 평면과 조그로 잡은 자세를 실행 가능한 레시피 YAML 로 낸다.
UI 는 본 서비스만 호출하고 파일을 직접 쓰지 않는다.

## 왜 좌표를 절대값으로 박지 않는가

레시피에 절대 TCP 를 박으면 팔레트가 1mm 만 움직여도 무효가 된다. 대신 이미 있는
두 잡을 쓴다 — 둘 다 «측정한 기준 프레임 + 상대 오프셋» 으로 이동하므로 재측정만
하면 그대로 재사용된다:

- 고정식  → `move_to_plane_pose`    (기준 = 4점으로 만든 평면. 중심·법선 기준 상대)
- 비고정식 → `move_to_landmark_pose` (기준 = 위치 마커 1점. 마커 Rz 로 돌린 프레임)

`frame_mode: rz_only` 를 쓰는 이유는 스키마 설명 그대로다 — 마커의 rx/ry 측정
산포가 레버암에서 증폭되지 않는다.

## 발행물

    고정식   <name>_cali.yaml · <name>_pick.yaml · <name>_place.yaml
    비고정식 <name>_marker_scan.yaml · <name>_pick.yaml · <name>_place.yaml

`scan_start_tcp` 이 없으면(= 저장된 측정 파일로 평면을 만든 경로) 고정식의 cali 는
발행하지 않는다 — 그 파일들을 만든 cali 레시피가 이미 있다는 뜻이고, 없는 시작
자세를 지어내면 그 레시피가 엉뚱한 곳으로 가기 때문이다. 이때 발행물은 2개다.

설계 근거: docs/adr/2026-08-24-pallet-teach-wizard.md
"""
import math
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import yaml

from ..tools.landmark_frame import FRAME_MODE_RZ_ONLY, pose_in_landmark_frame
from ..hardware.gripper import BACKENDS, SCHUNK, GripperBackend

# 4점 순회 배치 — 매크로의 DEFAULT_CORNER_PLAN 과 같은 순서여야 한다.
# 여기서 다시 정의하는 이유는 발행기가 ROS2·매크로 없이도 도는 순수 모듈이기 때문이다
# (테스트가 로봇 없이 레시피를 검증할 수 있어야 한다). 두 곳이 갈라지지 않도록
# test_pallet_teach_macros.py 가 둘의 일치를 검사한다.
CORNER_PLAN = ((4, 0.0, 0.0), (2, 1.0, 0.0), (1, 0.0, -1.0), (3, -1.0, 0.0))

MOUNT_FIXED = 'fixed'
MOUNT_FLOATING = 'floating'
MOUNTS = (MOUNT_FIXED, MOUNT_FLOATING)

# 파일명으로 쓸 수 있는 이름 — 경로 구분자·상위참조를 막는다(신뢰경계).
NAME_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')

POSE_KEYS = ('x', 'y', 'z', 'rx', 'ry', 'rz')

# ============================================================================
# 아래 값은 **창작하지 않는다** — `config/recipes/pallet5/pallet5_pick.yaml`(2026-08-19
# 실기 확정, 순환 75주기 59.9분 무중단 완주본)에서 그대로 옮겼다. 생성 레시피는
# 그 구조와 파라미터를 따르고 **티칭한 offset 만 갈아끼운다.**
#
# ⚠️ 임의로 바꾸면 안 되는 이유 (그 파일 헤더에 실기 근거가 적혀 있다):
#    · 접근은 파지면 **+20mm**(L자, 하강 정지 1회) — 크게 띄우면 경로가 달라진다
#    · 접촉 구간은 **3%** + `straight_path` — 법선 직선으로만 접근한다
#    · `decel_zone_mm: 0` — 이 레시피는 감속 구간을 쓰지 않는다
# ============================================================================
APPROACH_LIFT_MM = 20.0            # 파지면 위 접근/이탈 높이 (mm)
CLEAR_LIFT_MM = 250.0              # 최종 들어올림/빠짐 높이 (mm)
TRAVEL_VELOCITY = 20.0             # 접근·최종 이탈 속도 (%)
CONTACT_VELOCITY = 3.0             # 파지/안착·근접 이탈 속도 (%)
DECEL_ZONE_MM = 0.0                # 검증본은 감속 구간을 쓰지 않는다
APPROACH_DECEL_VELOCITY = 10.0     # 접근 잡의 decel_velocity
CONTACT_DECEL_VELOCITY = 3.0       # 그 외 잡의 decel_velocity
MAX_TILT_DEG = 30.0
MAX_RADIUS_MM = 200.0
GRIP_TIMEOUT_SEC = 15.0            # 파지/놓기 잡의 timeout (그리퍼 기종 무관)
GRIP_SETTLE_MS = 2000              # 그리퍼 동작 완료 대기 (ms)

# 최종 하강/상승을 어떤 직선으로 낼 것인가. 둘 다 실기에서 도는 방식이라
# 상황에 맞춰 사용자가 고른다 — 어느 한쪽이 항상 옳지 않다.
#
#   plane_normal : 평면 좌표계 이동(move_to_plane_pose) + straight_path.
#                  **평면 법선**을 따라 내려간다. 평면이 기울어도 그 기울기를 따른다.
#   tcp_linear   : move_linear. **공구 축**을 따라 내려간다.
#                  table-1_pick_tcplinear.yaml 등 실기 검증본이 쓰는 방식이다.
#
# 접근 자세가 이미 법선에 정렬돼 있으면 둘은 사실상 같은 경로가 된다. 갈리는 것은
# 공구 자세가 법선과 어긋나 있을 때다.
DESCENT_PLANE_NORMAL = 'plane_normal'
DESCENT_TCP_LINEAR = 'tcp_linear'
DESCENT_MODES = (DESCENT_PLANE_NORMAL, DESCENT_TCP_LINEAR)

# ⚠️ move_linear 의 velocity 는 **mm/s** 다 (평면 경로의 % 와 단위가 다르다).
#    값은 table-1_pick_tcplinear.yaml 실기본에서 그대로 가져왔다 — 10 / 50.
TCP_CONTACT_VELOCITY_MMS = 10.0    # 파지면 접촉 구간
TCP_TRAVEL_VELOCITY_MMS = 50.0     # 최종 이탈 구간

# 위치 마커 촬영 자세로 갈 때 먼저 들르는 상공 높이 (mm).
# 촬영 자세로 직행하면 팔레트·가드를 옆에서 들이받을 수 있어, 위에서 내려온다
# (사용자 지시 2026-08-24 — "위에서 선 접근 후 하강, 안전제일").
MARKER_VIEW_LIFT_MM = 200.0

# `move_to_landmark_pose` 의 `max_radius_mm` 여유 (mm).
# ⚠️ 실행기는 **3차원** 거리로 검사한다 — `√(x²+y²+z²)`(job_executor.py:2231).
#    평면 거리(x·y)만 보고 상한을 잡으면 상승 구간에서 z 가 커져 오거부된다
#    (2026-08-25 실기: 실제 487.20mm 인데 상한을 420.30mm 로 발행해 거부).
RADIUS_MARGIN_MM = 100.0

DEFAULT_SCAN_VELOCITY = 25.0       # 꼭짓점 순회 속도 (%) — cali 레시피용


def _round_pose(pose: Dict[str, float], digits: int = 3) -> Dict[str, float]:
    return {key: round(float(pose.get(key, 0.0)), digits) for key in POSE_KEYS}


def _radius_3d(pose: Dict[str, float]) -> float:
    """기준 프레임 원점에서 목표까지 3차원 거리 — 실행기의 `max_radius_mm` 검사와 같은 식."""
    return math.sqrt(float(pose.get('x', 0.0)) ** 2
                     + float(pose.get('y', 0.0)) ** 2
                     + float(pose.get('z', 0.0)) ** 2)


def snap_rotation_to_plane(pose: Dict[str, float]) -> Dict[str, float]:
    """회전을 평면 법선·팔레트 변에 강제로 맞춘다 — **기본으로 쓰지 않는다.**

    ⚠️ 기본값은 `snap_rotation=False` 다. 티칭한 회전값은 **오차가 아니라 사용자가
       의도해서 잡은 값**이다(2026-08-24 사용자 확인). 180/0/90 에서 벗어난 것을
       «조그 손떨림» 으로 단정해 지우면 제대로 잡은 자세를 망가뜨린다.

    켜면 이렇게 바뀐다 (위치 x·y·z 는 어느 경우에도 건드리지 않는다):

        rx → 180 · ry → 0 · rz → 가장 가까운 90° 배수

    쓸 곳: 회전을 아예 안 잡고 위치만 티칭한 경우처럼, 사용자가 **명시적으로**
    정렬을 원할 때만.
    """
    snapped = dict(pose)
    snapped['rx'] = 180.0
    snapped['ry'] = 0.0
    snapped['rz'] = float(round(float(pose.get('rz', 0.0)) / 90.0) * 90.0)
    return snapped


class PalletRecipeGenerator:
    """측정·티칭 결과 → 레시피 YAML 3개.

    파일 쓰기 외에는 부수효과가 없고 ROS2 에 의존하지 않는다 — 로봇 없이 테스트된다.
    """

    def __init__(self, recipe_dir: Optional[str] = None, package_root: Optional[str] = None,
                 gripper: Any = SCHUNK, descent: str = DESCENT_PLANE_NORMAL):
        if package_root is None:
            # ⚠️ `__file__` 로 직접 조립하지 않는다. colcon 이 build/ 에 소스 심링크를
            #    걸어 두므로 `abspath`(심링크 미해석)로 올라가면 **build/tm_task_manager**
            #    가 나오고, 레시피가 소스가 아니라 빌드 디렉토리에 저장된다
            #    (2026-08-24 실사고: 사용자 티칭 4건이 build/config/recipes 로 샜다).
            #    `paths` 는 `Path(__file__).resolve()` 로 심링크를 풀어 항상 소스를 준다.
            from .. import paths
            package_root = str(paths.PACKAGE_ROOT)
        self.package_root = package_root
        self.recipe_dir = recipe_dir or os.path.join(package_root, 'config', 'recipes')
        # 발행할 그리퍼 잡 계열. MK2=SCHUNK(schunk_*) · MK4=SMC(smc_*).
        # 이 클래스는 «ROS2 에 의존하지 않는다»(클래스 docstring)가 규약이라 여기서
        # 감지하지 않는다 — 감지는 매크로 층에서 끝내고 결과만 받는다.
        # ⚠️ 기본값이 SCHUNK 인 것은 기존 레시피·테스트와의 호환 때문이다. 운영
        #    경로(pallet_emit_recipes)는 항상 명시해 넘기므로 기본값에 기대지 않는다.
        self.gripper: GripperBackend = (
            gripper if isinstance(gripper, GripperBackend)
            else BACKENDS[str(gripper).strip().lower()])
        # 최종 하강/상승 방식. 기본값이 법선 직선인 것은 기존 발행물·테스트와의
        # 호환 때문이다 — 기본값을 바꾸면 이미 나간 레시피와 경로가 달라진다.
        mode = (descent or DESCENT_PLANE_NORMAL).strip().lower()
        if mode not in DESCENT_MODES:
            raise ValueError(
                '알 수 없는 하강 방식 %r — 가능한 값: %s'
                % (descent, ', '.join(DESCENT_MODES)))
        self.descent: str = mode

    # ------------------------------------------------------------------ 공개

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
        """레시피 3개를 쓰고 절대경로 목록을 돌려준다.

        Raises:
            ValueError: 이름·마운트·필수 입력이 잘못됨
            FileExistsError: 같은 이름이 이미 있고 overwrite 가 False
            OSError: 파일 쓰기 실패
        """
        self._validate(pallet_name, mount, plate_pose, teach_poses, marker_pose)

        # 평면 스냅샷을 먼저 남긴다 — pick/place 의 `load_plate_pose` 가 이걸 읽는다.
        # 이게 없으면 레시피가 «평면 pose 가 없습니다» 로 실패한다(2026-08-24 실기).
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
            # 저장된 측정 파일로 평면을 만든 경로에는 실측 시작 자세가 없다. 그 파일들을
            # 만든 cali 레시피가 이미 있다는 뜻이므로 새로 발행하지 않는다 — 없는 자세를
            # 지어내 레시피를 쓰면 그 레시피는 엉뚱한 곳으로 간다.
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

    # ----------------------------------------------------------------- 검증

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

    # --------------------------------------------------------------- 헤더

    @staticmethod
    def _header(name: str, summary: str, operator: str) -> Dict[str, Any]:
        """최상위 키를 기존 레시피(`pallet5_pick.yaml`)와 같게 맞춘다."""
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
        """잡 id 를 1부터 순차로 다시 매긴다.

        잡을 끼우거나 뺄 때마다 `step + N` 산술을 손보면 번호가 어긋난다
        (2026-08-25 실측: 상공 진입을 끼우자 [.., 11, 11, 11, 10] 이 나왔다).
        구성은 순서로만 하고 번호는 여기서 한 번에 확정한다.
        """
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
        """파지/놓기 잡. 잡 타입은 self.gripper 가 정한다 — 여기서 기종을 추측하지 않는다."""
        return self._job(job_id, self.gripper.job_type(closing),
                         self.gripper.job_name(closing), caption,
                         {'timeout': GRIP_TIMEOUT_SEC})

    def _settle_job(self, job_id: int) -> Dict[str, Any]:
        return self._job(job_id, 'wait', '대기', '그리퍼 동작 완료 대기',
                         {'duration': GRIP_SETTLE_MS})

    def _linear_job(self, job_id: int, caption: str, dz_mm: float,
                    velocity_mms: float) -> Dict[str, Any]:
        """공구 축 직선 이동. **양수 dz 가 하강**이다 (실기본 id6 = +20).

        파라미터 키에 공백이 들어간다(`offset X`) — 실행기가 그 이름으로 읽는다
        (bridge_executor `params.get(\"offset X\")`). 바꾸면 조용히 0 이 된다.
        """
        return self._job(job_id, 'move_linear', '직선 이동', caption, {
            'offset X': 0.0,
            'offset Y': 0.0,
            'offset Z': round(float(dz_mm), 3),
            'velocity': velocity_mms,
        })

    # ------------------------------------------------------- 고정식: 측정

    def _fixed_cali(self, pallet_name, scan_start_tcp, pitch_x, pitch_y,
                    trim_x, trim_y, operator) -> Dict[str, Any]:
        """4점 측정 레시피. 시작 자세는 티칭 때 4마커가 검출된 것이 확인된 자세다."""
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

    # ------------------------------------------------- 고정식: 픽/플레이스

    def _write_plate_snapshot(self, pallet_name, plate_pose, plate_marks,
                              operator) -> str:
        """티칭에 쓴 평면을 `calculate_plate_pose` 저장본과 **같은 모양**으로 남긴다.

        `load_plate_pose` 는 저장된 pose 값이 아니라 `landmarks` 의 jig1~4 를 평균해
        평면을 **재계산**한다. 따라서 마크를 반드시 함께 남겨야 하며, 형식이 다르면
        "jig1~4 가 모두 있지 않음" 으로 건너뛴다.
        """
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
        """픽/플레이스 첫 잡 — 티칭에 쓴 평면을 복원한다.

        `move_to_plane_pose` 는 실행기의 `detected_plate_pose` 를 쓰는데, 그것은
        같은 세션에서 `calculate_plate_pose`(또는 이 잡)가 돌아야 채워진다. 이 잡이
        없으면 레시피 단독 실행이 «평면 pose 가 없습니다» 로 즉시 실패한다.
        """
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
        """평면 좌표계 기준 픽 또는 플레이스.

        구조는 `config/recipes/pallet5/pallet5_pick.yaml`·`_place.yaml`(2026-08-19 실기
        확정본)과 **같다** — 잡 종류·순서·파라미터를 그대로 두고 `offset_*` 만
        티칭값으로 바꾼다. 회전(offset_rx/ry/rz)은 사용자 지시(2026-08-24)에 따라
        **티칭 생값을 그대로** 넣는다.

            pick : recipe_info · 그리퍼 열기 · 대기 · 평면 복원 ·
                   접근(+20) · 집기 · 파지 · 대기 · 들어올림(+20) · 들어올림(+250)
            place: recipe_info · 평면 복원 ·
                   접근(+20) · 놓기 · 놓음 · 대기 · 빠짐(+20) · 빠짐(+250)

        place 앞에 그리퍼 열기가 없는 이유는 그 시점에 박스를 들고 있기 때문이다.
        """
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
        # ⚠️ 첫 진입은 **최종 이탈과 같은 높이**(+250mm)로 온다. 곧바로 파지면 +20mm 로
        #    가면 팔레트 밖에서 낮게 접근해 가드를 옆으로 들이받을 수 있다
        #    (사용자 지시 2026-08-25 — "그 높이 그대로 접근 후 내려가서 잡게").
        jobs.append(plane_job(
            step + 1,
            f'상공 진입 ({target_word} 높이 +{CLEAR_LIFT_MM:.0f}mm)',
            clear, TRAVEL_VELOCITY, False, APPROACH_DECEL_VELOCITY))
        jobs.append(plane_job(
            step + 2,
            f'팔레트 위 접근 — 파지면 +{APPROACH_LIFT_MM:.0f}mm 위 (법선 하강)',
            near, TRAVEL_VELOCITY, True, APPROACH_DECEL_VELOCITY))
        # 최종 하강 → 파지 → 상승 2단. 여기만 하강 방식에 따라 갈린다.
        # 상공 진입·접근(위 두 잡)은 방식과 무관하게 같다 — 자세를 잡는 구간이다.
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

    # ----------------------------------------------- 비고정식: 마커 스캔

    def _marker_scan(self, pallet_name, marker_view_tcp, operator) -> Dict[str, Any]:
        """위치 마커 재측정 레시피. 실행 시점의 팔레트 위치를 알아내는 단계다."""
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
            # 그리퍼는 **닫는다**. 열면 턱이 벌어져 카메라 시야를 가린다
            # (사용자 지시 2026-08-24 — "촬영 전엔 그리퍼 grip, 카메라 안 가리게").
            self._grip_job(1, closing=True, caption='촬영 전 그리퍼 닫기 (카메라 시야 확보)'),
            self._job(2, 'wait', '대기', '그리퍼 안정화', {'duration': GRIP_SETTLE_MS}),
            # 상공 경유 → 하강. 촬영 자세로 직행하지 않는다.
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

    # ------------------------------------------- 비고정식: 픽/플레이스

    def _landmark_motion(self, pallet_name, marker_pose, teach_poses, slot,
                         operator, snap_rotation: bool = False) -> Dict[str, Any]:
        """마커 좌표계 기준 픽 또는 플레이스.

        티칭은 평면 기준으로 잡았지만 실행 기준은 위치 마커이므로, 저장해 둔 **절대**
        TCP 를 마커 프레임으로 환산한다(`pose_in_landmark_frame`). 평면 상대값을
        마커 상대값으로 바로 바꿀 수는 없다 — 두 프레임의 원점·회전이 다르다.
        """
        taught_absolute = teach_poses[slot]['absolute']
        taught = _round_pose(
            pose_in_landmark_frame(marker_pose, taught_absolute, FRAME_MODE_RZ_ONLY))
        if snap_rotation:
            taught = _round_pose(snap_rotation_to_plane(taught))

        near = dict(taught)
        near['z'] = round(taught['z'] + APPROACH_LIFT_MM, 3)
        clear = dict(taught)
        clear['z'] = round(taught['z'] + CLEAR_LIFT_MM, 3)

        # 상한은 **이 레시피가 실제로 내보내는 모든 목표** 중 최대 3D 거리 + 여유로 잡는다.
        # 실행기와 같은 식을 써야 오거부가 없다(job_executor.py:2231).
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
                # 마커가 움직이는 팔레트라 낡은 저장본은 위험하다 — 30분 넘으면 거부.
                'max_age_min': 30.0,
                'tool_offset_x': 0.0, 'tool_offset_y': 0.0, 'tool_offset_z': 0.0,
                'tool_offset_rx': 0.0, 'tool_offset_ry': 0.0, 'tool_offset_rz': 0.0,
                'velocity': velocity,
                'max_radius_mm': radius,
                'decel_zone_mm': DECEL_ZONE_MM,
                'decel_velocity': decel,
            })

        # 잡 순서는 고정식(`_plane_motion`)과 같다 — 기준 프레임만 마커로 바뀐다.
        jobs: List[Dict[str, Any]] = [
            self._recipe_info(1, f'{pallet_name} 에서 박스를 {verb}는다 (비고정식)', operator),
        ]
        if picking:
            jobs.append(self._grip_job(2, closing=False, caption='집기 전 그리퍼 열기'))
            jobs.append(self._settle_job(3))

        step = len(jobs) + 1
        # 첫 진입을 최종 이탈과 같은 높이로 — 고정식과 같은 이유(사용자 지시 2026-08-25).
        jobs.append(landmark_job(
            step,
            f'상공 진입 (+{CLEAR_LIFT_MM:.0f}mm)',
            clear, TRAVEL_VELOCITY, APPROACH_DECEL_VELOCITY))
        jobs.append(landmark_job(
            step + 1,
            f'마커 기준 접근 — 파지면 +{APPROACH_LIFT_MM:.0f}mm 위',
            near, TRAVEL_VELOCITY, APPROACH_DECEL_VELOCITY))
        # 고정식과 같은 지점에서 갈린다 — 기준 프레임만 마커일 뿐 구조는 동일하다.
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
