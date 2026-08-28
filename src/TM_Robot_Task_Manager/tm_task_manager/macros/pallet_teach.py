"""팔레트 티칭 매크로 — 4점 측정 → 중심 접근 → 조그 티칭 → 레시피 발행.

한 탭에서 버튼만 눌러 팔레트를 등록하는 마법사의 실행부다. UI 는 이 매크로들을
순서대로 부르기만 하고 계산·이동·파일 발행은 전부 여기서 한다.

## 왜 매크로인가

`macros/base.py` 가 이미 칠판(blackboard)·선행조건 검사·정적 순서 검증을 제공한다
(`run_macro` 가 `blackboard_requires` 미충족 시 실행 전에 막고, `validate_sequence`
가 Job 정의 시점에 순서 오류를 잡는다). 별도 마법사 서비스를 만들면 그 셋을 다시
구현하게 되므로 매크로로 등록한다.
설계 근거: docs/adr/2026-08-24-pallet-teach-wizard.md

## 칠판 사슬

    pallet_capture_marker  → position_marker_pose   (비고정식만 — 고정식은 건너뛴다)
    pallet_scan_4corners   → plate_pose, plate_marks, scan_start_tcp
    pallet_center_approach → approach_pose          (requires plate_pose)
    pallet_capture_teach   → teach_poses            (requires plate_pose)
    pallet_emit_recipes    → recipe_paths           (requires plate_pose, teach_poses)

`validate_sequence(['pallet_scan_4corners', ...])` 로 이 순서를 정적으로 검증할 수
있다 — 탭이 단계를 건너뛰면 로봇을 움직이기 전에 잡힌다.

## 좌표 계약

티칭 결과는 **평면(plate) 좌표계 상대값**으로 칠판에 남긴다
(`jig_plane_calculator.pose_in_plane_frame`). 절대 TCP 로 남기면 팔레트가 조금만
움직여도 무효가 되지만, 평면 상대값은 재측정한 평면에 그대로 얹을 수 있다 —
비고정식 팔레트가 성립하는 이유가 이것이다.
"""
import glob
import os
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .base import MacroContext, MacroResult, register
import numpy as np

from ..tools.jig_plane_calculator import (
    JigPlaneCalculator,
    _rotation_matrix_from_pose,
    pose_in_plane_frame,
    tcp_pose_for_plane_normal,
)

# 4점 순회 기본 배치. pallet0_cali.yaml 실측 순서를 그대로 옮겼다 —
# 1사분면에서 시작해 +X → -Y → -X 로 돌며 jig4 → jig2 → jig1 → jig3 을 찍는다.
# (dx, dy) 는 **직전 지점 기준 상대 이동**이고 jig 번호는 그 자리에서 찍을 지그다.
DEFAULT_CORNER_PLAN: Tuple[Tuple[int, float, float], ...] = (
    (4, 0.0, 0.0),      # 1사분면 — 사용자가 조그로 맞춰 둔 시작 지점
    (2, 1.0, 0.0),      # 2사분면 — +pitch_x
    (1, 0.0, -1.0),     # 3사분면 — -pitch_y
    (3, -1.0, 0.0),     # 4사분면 — -pitch_x
)

# 티칭 슬롯 — 레시피 생성기가 이 이름으로 찾는다.
TEACH_SLOTS = ('approach', 'pick', 'place')


def _current_tcp(ctx: MacroContext) -> Optional[List[float]]:
    """현재 TCP 6축을 읽는다. 못 읽으면 None.

    executor 의 비공개 상태를 건드리지 않으려고 ros_node 에서 직접 읽는다 —
    `job_executor` 도 같은 경로를 쓴다(`job_executor.py:420` 등).
    """
    node = ctx.ros_node
    pose = getattr(node, 'current_tcp_pose', None) if node else None
    if not pose or len(pose) < 6:
        return None
    return [float(v) for v in pose[:6]]


def _tcp_dict(pose: List[float]) -> Dict[str, float]:
    return {'x': pose[0], 'y': pose[1], 'z': pose[2],
            'rx': pose[3], 'ry': pose[4], 'rz': pose[5]}


def normalize_plate_pose_up(plate_pose: Dict[str, float]) -> Dict[str, float]:
    """평면 법선이 아래를 향하면 뒤집어 **항상 +Z(위)** 로 만든다.

    팔레트 면은 물리적으로 늘 위를 향한다 — 박스가 아래에 매달리지 않는다. 그런데
    `JigPlaneCalculator.calculate_plane_pose` 의 법선은 마크 1→4 의 **감김 방향**에서
    나오므로, 팔레트가 90° 돌아 놓이면 순서가 뒤집혀 법선이 아래를 가리킨다.

    그대로 두면 `목표 = 중심 + 법선 × standoff` 가 **팔레트 속**을 가리켜 로봇이
    갈 수 없는 자세가 되고, TMflow 가 컨트롤러 기능 라이브러리 에러로 거부한다
    (2026-08-24 실측: 평면 rx -180.00 · rz 176.43 → 목표 Z -406.33 = 평면 -150mm).
    티칭 상대좌표(`pose_in_plane_frame`)의 z 부호도 함께 뒤집혀 발행 레시피의
    `offset_z` 가 음수가 되고, `move_to_plane_pose` 는 그걸 거부한다.

    뒤집기는 **평면 X축 둘레 180° 회전**이다 — 법선과 Y축이 함께 반전되어
    오른손 좌표계가 유지된다(det=+1). 위치(x·y·z)는 건드리지 않는다.
    """
    rotation = _rotation_matrix_from_pose(plate_pose)
    if rotation[2, 2] >= 0:
        return dict(plate_pose)
    flipped = rotation @ np.diag([1.0, -1.0, -1.0])
    rx, ry, rz = JigPlaneCalculator._rotation_matrix_to_euler_zyx(flipped)
    out = dict(plate_pose)
    out['rx'], out['ry'], out['rz'] = rx, ry, rz
    return out


def package_root() -> str:
    """상대 저장경로 해석 기준 — `move_to_landmark_pose` 의 `source_path` 규약
    ("상대경로는 패키지 루트 기준")과 같은 뿌리를 쓴다.

    ⚠️ 직접 `__file__` 로 역산하지 않는다. `data/`·`ui/`·`config/` 는 파이썬 모듈
       디렉토리(`tm_task_manager/`)가 아니라 **그 위 ROS 패키지 루트**에 있어서,
       역산하면 한 단계 깊은 곳을 가리켜 파일을 하나도 못 찾는다(2026-08-24 실측).
       `paths.PACKAGE_ROOT` 가 그 단일 근원이다.
    """
    from .. import paths
    return str(paths.PACKAGE_ROOT)


def resolve_measurement_dir(source_path: str) -> str:
    if os.path.isabs(source_path):
        return source_path
    return os.path.normpath(os.path.join(package_root(), source_path))


def list_measurement_files(source_path: str, file_prefix: str = '',
                           max_files: int = 0) -> List[str]:
    """저장된 plate_pose 측정 파일을 **최신순**으로 고른다.

    `calculate_plate_pose` 의 `save_path` 가 남긴 파일들이다. 최신순인 이유는 팔레트를
    옮긴 뒤의 옛 측정이 섞이면 평균이 조용히 오염되기 때문이다 — 최근 것부터 쓴다.
    """
    directory = resolve_measurement_dir(source_path)
    if not os.path.isdir(directory):
        return []
    pattern = os.path.join(directory, f'{file_prefix}*.yaml' if file_prefix else '*.yaml')
    paths = [p for p in glob.glob(pattern) if os.path.isfile(p)]
    paths.sort(key=os.path.getmtime, reverse=True)
    if max_files and max_files > 0:
        paths = paths[:max_files]
    return paths


def average_marks_with_outliers(file_paths: List[str],
                                outlier_method: str = 'iqr') -> Tuple[
        Optional[List[Dict[str, float]]], List[str], List[Tuple[str, str]], Dict[int, Dict]]:
    """여러 측정 파일의 jig1~4 를 **outlier 제거 후** 평균낸다.

    `jig_plane_calculator.average_landmarks_from_files` 는 단순 평균만 하므로 쓰지
    않는다 — 한 번 튄 측정이 그대로 중심을 끌고 간다. 대신 꼭짓점마다
    `LandmarkAnalyzer` 를 물려 스캔 반복에 쓰는 것과 **같은 outlier 규칙**(iqr·3sigma)을
    파일 간에도 적용한다.

    Returns:
        (jig1~4 순서 마크 4개 | None, 사용한 파일, [(건너뛴 파일, 사유)], 꼭짓점별 통계)
    """
    from ..services.landmark_analyzer import LandmarkAnalyzer

    keys = ('x', 'y', 'z', 'rx', 'ry', 'rz')
    analyzers = {index: LandmarkAnalyzer() for index in range(1, 5)}
    used: List[str] = []
    skipped: List[Tuple[str, str]] = []

    for path in file_paths:
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                data = yaml.safe_load(handle) or {}
        except (OSError, yaml.YAMLError) as exc:
            skipped.append((path, f"읽기 실패: {exc}"))
            continue

        landmarks = data.get('landmarks') or {}
        if not all(f'jig{i}' in landmarks for i in range(1, 5)):
            skipped.append((path, "jig1~4 가 모두 있지 않음"))
            continue

        for index in range(1, 5):
            mark = landmarks[f'jig{index}']
            analyzers[index].add_measurement(*(float(mark.get(k, 0.0)) for k in keys))
        used.append(path)

    if not used:
        return None, used, skipped, {}

    marks: List[Dict[str, float]] = []
    stats: Dict[int, Dict] = {}
    for index in range(1, 5):
        analysis = analyzers[index].analyze(outlier_method, 'xyz')
        pose = analyzers[index].get_final_pose(outlier_method, 'xyz')
        if not pose.get('detected'):
            return None, used, skipped, stats
        mark = {k: float(pose[k]) for k in keys}
        mark['detected'] = True
        mark['jig_number'] = index
        marks.append(mark)
        stats[index] = analysis

    return marks, used, skipped, stats


@register(
    name='pallet_load_measurements',
    summary='이미 저장된 측정 파일 여러 개를 골라 outlier 제거 후 평균내 평면을 만든다. '
            '로봇을 움직이지 않으므로 4점 측정을 건너뛰고 바로 티칭으로 갈 수 있다.',
    category='Calibration',
    params={
        'source_path': {'type': 'dirpath', 'default': 'data/plate_pose_calc',
                        'description': '측정 파일 폴더 (상대경로는 패키지 루트 기준)'},
        'file_prefix': {'type': 'str', 'default': '',
                        'description': '파일명 접두어 (비우면 폴더 전체)'},
        'max_files': {'type': 'int', 'default': 5, 'min': 0, 'max': 100,
                      'description': '최신 파일 몇 개를 쓸지 (0=전부). file_paths 를 주면 무시'},
        'outlier_method': {'type': 'choice', 'default': 'iqr',
                           'choices': ['none', 'iqr', '3sigma'],
                           'description': '파일 간 outlier 제거 방법'},
        'file_paths': {'type': 'list', 'default': None,
                       'description': '쓸 파일을 직접 지정 (화면에서 고른 목록). '
                                      '주면 source_path 검색을 건너뛴다'},
    },
    produces=['plate_pose', 'plate_marks', 'measurement_sources'],
)
def pallet_load_measurements(ctx: MacroContext,
                             source_path: str = 'data/plate_pose_calc',
                             file_prefix: str = '',
                             max_files: int = 5,
                             outlier_method: str = 'iqr',
                             file_paths: Optional[List[str]] = None) -> MacroResult:
    paths = list(file_paths) if file_paths else list_measurement_files(
        source_path, file_prefix, max_files)
    if not paths:
        return MacroResult.failure(
            f"측정 파일을 찾지 못했습니다 — {resolve_measurement_dir(source_path)} 에 "
            f"'{file_prefix or '*'}*.yaml' 이 없습니다"
        )

    marks, used, skipped, stats = average_marks_with_outliers(paths, outlier_method)
    for path, reason in skipped:
        ctx.log(f"  건너뜀: {os.path.basename(path)} — {reason}")
    if marks is None:
        return MacroResult.failure(
            f"쓸 수 있는 측정이 없습니다 (후보 {len(paths)}개, 건너뜀 {len(skipped)}개) — "
            "jig1~4 가 모두 들어 있는 파일이 필요합니다"
        )
    # 파일 1개면 평균·outlier 가 의미 없다. 막지는 않되 그 사실을 드러낸다 —
    # 사용자가 '여러 개 골라 평균' 을 의도했는데 1개만 잡힌 경우를 조용히 넘기지 않는다.
    if len(used) == 1:
        ctx.log("  ⚠ 파일이 1개입니다 — 평균·outlier 제거가 적용되지 않습니다")

    calculator = JigPlaneCalculator()
    if not calculator.load_from_dicts(marks):
        return MacroResult.failure("평균 마크 로드 실패 — 배치를 확인하세요")
    plate_pose = calculator.to_dict()
    if plate_pose is None:
        return MacroResult.failure("평면 pose 계산 실패 — 평균 마크 배치가 퇴화했습니다")

    # 법선을 항상 위로 — 마크 감김 방향에 좌우되지 않게 한다
    plate_pose = normalize_plate_pose_up(plate_pose)
    ctx.put('plate_pose', plate_pose)
    ctx.put('plate_marks', marks)
    ctx.put('measurement_sources', list(used))
    # 이 경로에는 실측 시작 자세가 없다. cali 레시피는 이 파일들을 만든 기존 레시피가
    # 이미 있으므로 새로 발행하지 않는다(발행기가 None 을 보고 건너뛴다).
    ctx.blackboard.pop('scan_start_tcp', None)

    removed = sum(s.get('outliers_removed', 0) for s in stats.values())
    message = (f"측정 {len(used)}개 평균 완료 (outlier {outlier_method}, {removed}개 제거) — "
               f"중심 (X{plate_pose['x']:.2f} Y{plate_pose['y']:.2f} Z{plate_pose['z']:.2f})")
    ctx.log(message)
    for path in used:
        ctx.log(f"  사용: {os.path.basename(path)}")
    return MacroResult.success(message, plate_pose=plate_pose,
                               measurement_sources=list(used))


@register(
    name='pallet_capture_marker',
    summary='비고정식 팔레트의 위치 마커를 측정해 칠판과 파일에 남긴다. 실행 시점에 '
            '이 마커를 다시 찍어 팔레트가 어디로 옮겨졌는지 알아낸다.',
    category='Calibration',
    params={
        'repeat_count': {'type': 'int', 'default': 10, 'min': 1, 'max': 30,
                         'description': '반복 측정 횟수'},
        'outlier_method': {'type': 'choice', 'default': '3sigma',
                           'choices': ['none', 'iqr', '3sigma'],
                           'description': 'Outlier 제거 방법'},
        'wait_after_command': {'type': 'int', 'default': 0, 'step': 100,
                               'description': '스캔 명령 후 대기 (ms)'},
    },
    produces=['position_marker_pose', 'marker_view_tcp'],
)
def pallet_capture_marker(ctx: MacroContext,
                          repeat_count: int = 10,
                          outlier_method: str = '3sigma',
                          wait_after_command: int = 0) -> MacroResult:
    view = _current_tcp(ctx)
    if view is None:
        return MacroResult.failure("현재 TCP 를 읽지 못했습니다")

    if ctx.is_stop_requested:
        return MacroResult.failure("정지 요청으로 위치 마커 측정을 중단했습니다")

    pose, _ = ctx.scan_landmark_averaged(
        repeat_count, outlier_method, wait_after_command / 1000.0,
        jig_number=None, analysis_target='xyz_rx_ry_rz',
    )
    if pose is None:
        return MacroResult.failure(
            "위치 마커 미검출 — 유효 측정 0건입니다. 마커가 화면에 들어오는지 확인하세요"
        )

    marker = {key: float(pose[key]) for key in ('x', 'y', 'z', 'rx', 'ry', 'rz')}
    ctx.put('position_marker_pose', marker)
    ctx.put('marker_view_tcp', _tcp_dict(view))

    message = (f"위치 마커 저장 — (X{marker['x']:.2f} Y{marker['y']:.2f} Z{marker['z']:.2f}) "
               f"· Rz {marker['rz']:.2f}°")
    ctx.log(message)
    return MacroResult.success(message, position_marker_pose=marker)


@register(
    name='pallet_scan_4corners',
    summary='1사분면 마커에서 시작해 마커 간격만큼 이동하며 꼭짓점 4개를 측정하고 '
            '평면(plate) pose 를 계산한다. 시작 자세는 사용자가 조그로 맞춰 둔 것을 쓴다.',
    category='Calibration',
    params={
        'pitch_x': {'type': 'float', 'default': 0.0, 'min': 0.0,
                    'description': '마커 가로 간격 (mm) — 팔레트 고유값'},
        'pitch_y': {'type': 'float', 'default': 0.0, 'min': 0.0,
                    'description': '마커 세로 간격 (mm) — 팔레트 고유값'},
        'trim_x': {'type': 'float', 'default': 0.0,
                   'description': '마지막 지점 X 보정 (mm) — 마커 부착 편차 흡수'},
        'trim_y': {'type': 'float', 'default': 0.0,
                   'description': '마지막 지점 Y 보정 (mm) — 마커 부착 편차 흡수'},
        'velocity': {'type': 'float', 'default': 25.0, 'min': 1.0, 'max': 100.0,
                     'description': '꼭짓점 사이 이동 속도 (%)'},
        'repeat_count': {'type': 'int', 'default': 10, 'min': 1, 'max': 30,
                         'description': '지점당 반복 측정 횟수'},
        'outlier_method': {'type': 'choice', 'default': '3sigma',
                           'choices': ['none', 'iqr', '3sigma'],
                           'description': 'Outlier 제거 방법'},
        'wait_after_command': {'type': 'int', 'default': 0, 'step': 100,
                               'description': '스캔 명령 후 대기 (ms)'},
    },
    produces=['plate_pose', 'plate_marks', 'scan_start_tcp'],
)
def pallet_scan_4corners(ctx: MacroContext,
                         pitch_x: float = 0.0,
                         pitch_y: float = 0.0,
                         trim_x: float = 0.0,
                         trim_y: float = 0.0,
                         velocity: float = 25.0,
                         repeat_count: int = 10,
                         outlier_method: str = '3sigma',
                         wait_after_command: int = 0) -> MacroResult:
    if pitch_x <= 0 or pitch_y <= 0:
        return MacroResult.failure(
            "마커 간격(가로·세로)이 필요합니다 — 1사분면에서 나머지 3점으로 갈 거리를 "
            "모르면 측정을 시작할 수 없습니다"
        )

    start = _current_tcp(ctx)
    if start is None:
        return MacroResult.failure("현재 TCP 를 읽지 못했습니다 — 로봇 상태 채널을 확인하세요")

    # 시작 자세(Rx/Ry/Rz)는 유지한다 — 사용자가 4마커가 보이도록 맞춰 둔 자세다.
    ctx.log(f"[팔레트] 4점 측정 시작 — 간격 {pitch_x:.1f} × {pitch_y:.1f}mm, "
            f"시작 (X{start[0]:.1f} Y{start[1]:.1f} Z{start[2]:.1f})")

    marks: List[Dict[str, float]] = []
    cx, cy = 0.0, 0.0
    for order, (jig_number, ux, uy) in enumerate(DEFAULT_CORNER_PLAN, start=1):
        cx += ux * pitch_x
        cy += uy * pitch_y
        if order == len(DEFAULT_CORNER_PLAN):
            cx += trim_x
            cy += trim_y

        if order > 1:
            moved, message = ctx.move_to_position(
                'tcp',
                start[0] + cx, start[1] + cy, start[2],
                start[3], start[4], start[5],
                velocity,
            )
            ctx.log(message)
            if not moved:
                return MacroResult.failure(
                    f"{order}번째 꼭짓점 이동 실패 — 측정을 중단합니다 (jig{jig_number})"
                )

        if ctx.is_stop_requested:
            return MacroResult.failure("정지 요청으로 4점 측정을 중단했습니다")

        pose, _ = ctx.scan_landmark_averaged(
            repeat_count, outlier_method, wait_after_command / 1000.0,
            jig_number=jig_number, analysis_target='xyz',
        )
        if pose is None:
            return MacroResult.failure(
                f"jig{jig_number} 미검출 — {order}번째 꼭짓점에서 유효 측정이 0건입니다. "
                f"조명·렌즈 거리를 확인하고 이 단계부터 다시 실행하세요"
            )
        mark = dict(pose)
        mark['detected'] = True
        mark['jig_number'] = jig_number
        marks.append(mark)
        ctx.log(f"  jig{jig_number}: X={mark['x']:.2f} Y={mark['y']:.2f} Z={mark['z']:.2f}")

    # ⚠️ 순회 순서(jig4 → jig2 → jig1 → jig3)가 아니라 **jig 번호 순**으로 넣는다.
    #    `JigPlaneCalculator.calculate_plane_pose` 는 위치 인덱스로 축을 만들기 때문이다
    #    (v_x = m[2]-m[0], v_y = m[1]-m[0]). 스캔 순서 그대로 주면 축이 뒤엉켜
    #    평면 계산이 실패하거나 법선이 뒤집힌다. `_exec_calculate_plate_pose` 도
    #    `for i in range(1, 5)` 로 같은 순서를 만든다(job_executor.py:2037).
    ordered = [mark for _, mark in sorted(
        ((int(mark['jig_number']), mark) for mark in marks), key=lambda pair: pair[0])]

    calculator = JigPlaneCalculator()
    if not calculator.load_from_dicts(ordered):
        return MacroResult.failure("Landmark 4점 로드 실패 — 평면을 계산할 수 없습니다")

    plate_pose = calculator.to_dict()
    if plate_pose is None:
        return MacroResult.failure("평면 pose 계산 실패")

    # 법선을 항상 위로 — 마크 감김 방향에 좌우되지 않게 한다
    plate_pose = normalize_plate_pose_up(plate_pose)
    ctx.put('plate_pose', plate_pose)
    ctx.put('plate_marks', ordered)
    # 1사분면 시작 자세 — cali 레시피의 첫 이동 지점이 된다. 이 자세에서 4마커가
    # 검출된다는 것이 실측으로 확인된 셈이므로 그대로 레시피에 박는다.
    ctx.put('scan_start_tcp', _tcp_dict(start))

    message = (f"평면 계산 완료 — 중심 (X{plate_pose['x']:.2f} Y{plate_pose['y']:.2f} "
               f"Z{plate_pose['z']:.2f}) · 자세 ({plate_pose['rx']:.2f}, "
               f"{plate_pose['ry']:.2f}, {plate_pose['rz']:.2f})°")
    ctx.log(message)
    return MacroResult.success(message, plate_pose=plate_pose, plate_marks=marks)


@register(
    name='pallet_center_approach',
    summary='측정한 평면의 중심 위 standoff 높이로, 팔레트에 정렬해 이동한다. '
            '공구 면이 평면과 평행해지고(기울기 추종) 공구 회전이 팔레트 긴 변에 맞는다.',
    category='Calibration',
    params={
        'standoff_mm': {'type': 'float', 'default': 150.0, 'min': 1.0,
                        'description': '평면에서 띄울 거리 (mm)'},
        # 기본은 plane — 티칭 시작 자세는 «팔레트에 맞춰진» 상태여야 조그가 적게 든다
        # (사용자 지시 2026-08-24). keep 은 지금 잡아 둔 공구 회전을 그대로 두는 경우용.
        'rz_mode': {'type': 'choice', 'default': 'plane', 'choices': ['plane', 'keep'],
                    'description': "plane=팔레트 긴 변에 회전 정렬(기본) · "
                                   "keep=현재 공구 회전 유지. 기울기는 두 경우 모두 평면을 따른다"},
        'velocity': {'type': 'float', 'default': 20.0, 'min': 1.0, 'max': 100.0,
                     'description': '이동 속도 (%)'},
    },
    requires=['plate_pose'],
    produces=['approach_pose'],
)
def pallet_center_approach(ctx: MacroContext,
                           standoff_mm: float = 150.0,
                           rz_mode: str = 'plane',
                           velocity: float = 20.0) -> MacroResult:
    """평면 중심 위로 **팔레트에 정렬해** 이동한다.

    `tcp_pose_for_plane_normal` 은 공구 Z 를 항상 `-법선` 으로 놓으므로 **기울기는
    rz_mode 와 무관하게** 평면을 따른다(실측 2026-08-24: 공구 Z ↔ 법선 각차 0.0000°).
    `rz_mode` 가 정하는 것은 **법선축 둘레의 회전**뿐이다:

        plane : 평면 Y축(긴 변)에 맞춘다 → Rz ≈ 평면 Rz + 90
        keep  : 지금 공구 회전을 유지한다

    실측 대조 (pallet0, 평면 Rz 89.576 · 기울기 0.270°):
        keep  → Rx 179.739 Ry  0.066 Rz  -90.000
        plane → Rx 179.936 Ry -0.262 Rz  179.576
    """
    plate_pose = ctx.get('plate_pose')
    current = _current_tcp(ctx)
    if current is None:
        return MacroResult.failure("현재 TCP 를 읽지 못했습니다")

    try:
        target = tcp_pose_for_plane_normal(plate_pose, standoff_mm, rz_mode, current)
    except ValueError as exc:
        return MacroResult.failure(f"접근 자세 계산 실패: {exc}")

    alignment = '팔레트 긴 변 정렬' if rz_mode == 'plane' else '현재 공구 회전 유지'
    ctx.log(f"[팔레트] 중심 위 {standoff_mm:.0f}mm 로 이동 ({alignment}) — "
            f"(X{target['x']:.2f} Y{target['y']:.2f} Z{target['z']:.2f}) "
            f"자세 ({target['rx']:.2f}, {target['ry']:.2f}, {target['rz']:.2f})°")

    moved, message = ctx.move_to_position(
        'tcp',
        target['x'], target['y'], target['z'],
        target['rx'], target['ry'], target['rz'],
        velocity,
    )
    ctx.log(message)
    if not moved:
        return MacroResult.failure(f"중심 접근 이동 실패 — {message}")

    ctx.put('approach_pose', target)
    return MacroResult.success(
        f"중심 접근 완료 ({alignment}) — 조그로 상세 티칭하세요", approach_pose=target)


@register(
    name='pallet_capture_teach',
    summary='지금 로봇이 서 있는 자세를 평면 좌표계 상대값으로 환산해 티칭 슬롯에 담는다. '
            '절대좌표가 아니라 상대값이라 팔레트를 옮겨도 재사용된다.',
    category='Calibration',
    params={
        'slot': {'type': 'choice', 'default': 'pick', 'choices': list(TEACH_SLOTS),
                 'description': '이 자세를 담을 슬롯'},
    },
    requires=['plate_pose'],
    produces=['teach_poses'],
)
def pallet_capture_teach(ctx: MacroContext, slot: str = 'pick') -> MacroResult:
    if slot not in TEACH_SLOTS:
        return MacroResult.failure(f"알 수 없는 티칭 슬롯: {slot} (가능: {', '.join(TEACH_SLOTS)})")

    plate_pose = ctx.get('plate_pose')
    current = _current_tcp(ctx)
    if current is None:
        return MacroResult.failure("현재 TCP 를 읽지 못했습니다")

    absolute = _tcp_dict(current)
    relative = pose_in_plane_frame(plate_pose, absolute)

    # 평면 상대값과 절대 TCP 를 **둘 다** 남긴다. 고정식 레시피는 평면 상대값을
    # 그대로 쓰지만, 비고정식은 위치 마커 프레임으로 다시 환산해야 하므로
    # (pose_in_landmark_frame) 절대값이 있어야 한다. 여기서 두 프레임을 모두
    # 계산하지 않는 이유는 마커가 아직 없을 수도 있기 때문이다 — 환산은 발행 시점에 한다.
    poses: Dict[str, Dict[str, Any]] = dict(ctx.get('teach_poses') or {})
    poses[slot] = {'plane': relative, 'absolute': absolute}
    ctx.put('teach_poses', poses)

    message = (f"'{slot}' 티칭 저장 — 평면 기준 (x{relative['x']:.2f} y{relative['y']:.2f} "
               f"z{relative['z']:.2f}) · rz {relative['rz']:.2f}°")
    ctx.log(message)
    return MacroResult.success(message, teach_poses=poses)


@register(
    name='pallet_emit_recipes',
    summary='측정한 평면과 티칭 자세로 픽앤플레이스 레시피를 발행한다. '
            '고정식은 절대좌표, 비고정식은 마커 기준 상대좌표로 낸다.',
    category='Calibration',
    params={
        'pallet_name': {'type': 'str', 'default': '',
                        'description': '팔레트 이름 — 레시피 파일명이 된다'},
        'mount': {'type': 'choice', 'default': 'fixed', 'choices': ['fixed', 'floating'],
                  'description': 'fixed=고정식 · floating=비고정식(위치 마커 기준)'},
        'pitch_x': {'type': 'float', 'default': 0.0, 'description': '마커 가로 간격 (mm)'},
        'pitch_y': {'type': 'float', 'default': 0.0, 'description': '마커 세로 간격 (mm)'},
        'trim_x': {'type': 'float', 'default': 0.0, 'description': '마지막 지점 X 보정 (mm)'},
        'trim_y': {'type': 'float', 'default': 0.0, 'description': '마지막 지점 Y 보정 (mm)'},
        'operator': {'type': 'str', 'default': '', 'description': '작업자 이름'},
        'gripper': {'type': 'choice', 'default': '', 'choices': ['', 'smc', 'schunk'],
                    'description': '그리퍼 기종 — 비우면 감지 결과를 쓴다 (SMC→SCHUNK 순)'},
        'descent': {'type': 'choice', 'default': 'plane_normal',
                    'choices': ['plane_normal', 'tcp_linear'],
                    'description': '최종 하강/상승 직선 — plane_normal=평면 법선 · '
                                   'tcp_linear=공구 축'},
        'overwrite': {'type': 'bool', 'default': False,
                      'description': '같은 이름의 레시피가 있으면 덮어쓴다'},
    },
    requires=['plate_pose', 'teach_poses'],
    produces=['recipe_paths'],
)
def pallet_emit_recipes(ctx: MacroContext,
                        pallet_name: str = '',
                        mount: str = 'fixed',
                        pitch_x: float = 0.0,
                        pitch_y: float = 0.0,
                        trim_x: float = 0.0,
                        trim_y: float = 0.0,
                        operator: str = '',
                        gripper: str = '',
                        descent: str = 'plane_normal',
                        overwrite: bool = False) -> MacroResult:
    from ..services.pallet_recipe_generator import PalletRecipeGenerator

    name = (pallet_name or '').strip()
    if not name:
        return MacroResult.failure("팔레트 이름을 입력하세요 — 레시피 파일명이 됩니다")

    teach_poses = ctx.get('teach_poses') or {}
    missing = [slot for slot in ('pick', 'place') if slot not in teach_poses]
    if missing:
        return MacroResult.failure(
            f"티칭이 부족합니다 — {', '.join(missing)} 자세를 먼저 저장하세요"
        )

    if mount == 'floating' and not ctx.has('position_marker_pose'):
        return MacroResult.failure(
            "비고정식은 위치 마커가 필요합니다 — [위치 마커 촬영]을 먼저 수행하세요"
        )

    # 그리퍼 기종은 여기서 확정한다 — 발행기는 ROS2 를 모르는 순수 모듈이라
    # 감지를 그쪽에 두면 «로봇 없이 테스트된다» 규약이 깨진다.
    from ..hardware.gripper import NoGripperDetected
    from ..hardware.gripper import resolve as resolve_gripper
    try:
        backend = resolve_gripper(gripper, ctx.ros_node)
    except NoGripperDetected as exc:
        return MacroResult.failure(str(exc))
    ctx.log('[팔레트 티칭] 그리퍼 = %s (%s / %s)'
            % (backend.label, backend.grip, backend.release))

    try:
        generator = PalletRecipeGenerator(gripper=backend, descent=descent)
    except ValueError as exc:
        return MacroResult.failure(str(exc))
    ctx.log('[팔레트 티칭] 최종 하강/상승 = %s' % generator.descent)
    try:
        paths = generator.emit(
            pallet_name=name,
            mount=mount,
            plate_pose=ctx.get('plate_pose'),
            teach_poses=teach_poses,
            scan_start_tcp=ctx.get('scan_start_tcp'),
            marker_pose=ctx.get('position_marker_pose'),
            marker_view_tcp=ctx.get('marker_view_tcp'),
            # 평면 스냅샷용 — 이게 없으면 pick/place 가 평면을 복원하지 못해
            # «평면 pose 가 없습니다» 로 실패한다(2026-08-24 실기).
            plate_marks=ctx.get('plate_marks'),
            pitch_x=pitch_x, pitch_y=pitch_y,
            trim_x=trim_x, trim_y=trim_y,
            operator=operator,
            overwrite=overwrite,
        )
    except FileExistsError as exc:
        return MacroResult.failure(f"{exc} — 덮어쓰려면 [덮어쓰기]를 켜세요")
    except (ValueError, OSError) as exc:
        return MacroResult.failure(f"레시피 발행 실패: {exc}")

    ctx.put('recipe_paths', paths)
    for path in paths:
        ctx.log(f"  발행: {path}")
    message = f"레시피 {len(paths)}개 발행 완료 ({'고정식' if mount == 'fixed' else '비고정식'})"
    ctx.log(message)
    return MacroResult.success(message, recipe_paths=paths)
