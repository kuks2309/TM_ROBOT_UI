"""팔레트 티칭 마법사 — 매크로 계약과 레시피 발행 검증.

로봇·ROS2 없이 돈다. 매크로는 가짜 executor 로, 발행기는 임시 디렉토리로 검증한다.
"""
import math
import os
import sys
import tempfile
import unittest

import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tm_task_manager.macros import MACROS, validate_sequence  # noqa: E402
from tm_task_manager.macros.base import MacroContext  # noqa: E402
from tm_task_manager.macros.pallet_teach import DEFAULT_CORNER_PLAN  # noqa: E402
from tm_task_manager.services.pallet_recipe_generator import (  # noqa: E402
    CORNER_PLAN,
    PalletRecipeGenerator,
)


class FakeNode:
    def __init__(self, tcp):
        self.current_tcp_pose = list(tcp)


class FakeExecutor:
    """MacroContext 가 건드리는 표면만 흉내낸다."""

    def __init__(self, tcp=(800.0, 300.0, -200.0, 180.0, 0.0, -90.0), marks=None):
        self.ros_node = FakeNode(tcp)
        self.vision_manager = object()
        self.vision_origin_check_service = None
        self.coordinate_system_manager = None
        self._stop_requested = False
        self.logs = []
        self.moves = []
        self.pose_keeps = []
        self.pose_keep_ok = True
        self.move_ok = True
        self._marks = marks or {}

    def _log(self, message):
        self.logs.append(message)

    def _move_to_position(self, motion_type, x, y, z, rx, ry, rz, velocity,
                          decomposed_tcp=False):
        self.moves.append((x, y, z))
        if not self.move_ok:
            return False, "이동 실패: 로봇이 명령을 거부함 (테스트)"
        self.ros_node.current_tcp_pose = [x, y, z, rx, ry, rz]
        return True, f"이동 완료 ({x:.1f}, {y:.1f}, {z:.1f})"

    def _move_pose_keep(self, label, target, velocity,
                        decel_zone_mm=0.0, decel_velocity=3.0, straight=False):
        self.pose_keeps.append((label, dict(target), velocity, decel_zone_mm))
        self.ros_node.current_tcp_pose = [target['x'], target['y'], target['z'],
                                          target['rx'], target['ry'], target['rz']]
        return self.pose_keep_ok

    def scan_landmark_averaged(self, repeat_count, outlier_method, wait_time,
                               jig_number=None, analysis_target='xyz'):
        pose = self._marks.get(jig_number)
        if pose is None:
            return None, None
        return dict(pose), {}


# 200 × 140 직사각형을 base XY 평면에 눕힌 배치 (Z 동일).
SQUARE_MARKS = {
    4: {'x': 800.0, 'y': 300.0, 'z': -400.0, 'rx': 180.0, 'ry': 0.0, 'rz': 0.0},
    2: {'x': 940.0, 'y': 300.0, 'z': -400.0, 'rx': 180.0, 'ry': 0.0, 'rz': 0.0},
    1: {'x': 940.0, 'y': 100.0, 'z': -400.0, 'rx': 180.0, 'ry': 0.0, 'rz': 0.0},
    3: {'x': 800.0, 'y': 100.0, 'z': -400.0, 'rx': 180.0, 'ry': 0.0, 'rz': 0.0},
}


class MacroRegistrationTest(unittest.TestCase):
    def test_macros_registered(self):
        for name in ('pallet_capture_marker', 'pallet_scan_4corners',
                     'pallet_center_approach', 'pallet_capture_teach',
                     'pallet_emit_recipes'):
            self.assertIn(name, MACROS, f"{name} 이 레지스트리에 없습니다")

    def test_fixed_sequence_valid(self):
        ok, problems = validate_sequence(
            ['pallet_scan_4corners', 'pallet_center_approach',
             'pallet_capture_teach', 'pallet_emit_recipes'])
        self.assertTrue(ok, f"고정식 순서가 검증에 실패했습니다: {problems}")

    def test_floating_sequence_valid(self):
        ok, problems = validate_sequence(
            ['pallet_capture_marker', 'pallet_scan_4corners',
             'pallet_center_approach', 'pallet_capture_teach',
             'pallet_emit_recipes'])
        self.assertTrue(ok, f"비고정식 순서가 검증에 실패했습니다: {problems}")

    def test_out_of_order_rejected(self):
        """접근을 측정보다 먼저 두면 정적 검사가 잡아야 한다."""
        ok, problems = validate_sequence(
            ['pallet_center_approach', 'pallet_scan_4corners'])
        self.assertFalse(ok)
        self.assertTrue(any('plate_pose' in p for p in problems), problems)

    def test_corner_plan_matches_generator(self):
        """매크로와 발행기의 순회 배치가 갈라지면 측정과 레시피가 어긋난다."""
        self.assertEqual(tuple(DEFAULT_CORNER_PLAN), tuple(CORNER_PLAN))


class ScanMacroTest(unittest.TestCase):
    def _run(self, macro, ctx, **params):
        from tm_task_manager.macros import run_macro
        return run_macro(macro, ctx, params)

    def test_scan_requires_pitch(self):
        ctx = MacroContext(FakeExecutor(), {})
        result = self._run('pallet_scan_4corners', ctx, pitch_x=0.0, pitch_y=200.0)
        self.assertFalse(result.ok)
        self.assertIn('마커 간격', result.message)

    def test_scan_produces_plate_pose(self):
        executor = FakeExecutor(tcp=(800.0, 300.0, -200.0, 180.0, 0.0, -90.0),
                                marks=SQUARE_MARKS)
        ctx = MacroContext(executor, {})
        result = self._run('pallet_scan_4corners', ctx, pitch_x=140.0, pitch_y=200.0)
        self.assertTrue(result.ok, result.message)
        self.assertIn('plate_pose', ctx.blackboard)
        self.assertIn('scan_start_tcp', ctx.blackboard)
        self.assertEqual(len(ctx.get('plate_marks')), 4)
        # 3회 이동(1사분면은 제자리)
        self.assertEqual(len(executor.moves), 3)

    def test_scan_reports_undetected_corner(self):
        marks = dict(SQUARE_MARKS)
        marks.pop(1)
        executor = FakeExecutor(marks=marks)
        ctx = MacroContext(executor, {})
        result = self._run('pallet_scan_4corners', ctx, pitch_x=140.0, pitch_y=200.0)
        self.assertFalse(result.ok)
        self.assertIn('jig1', result.message)

    def test_capture_teach_requires_plate_pose(self):
        ctx = MacroContext(FakeExecutor(), {})
        result = self._run('pallet_capture_teach', ctx, slot='pick')
        self.assertFalse(result.ok)
        self.assertIn('plate_pose', result.message)

    def test_capture_teach_stores_both_frames(self):
        executor = FakeExecutor(marks=SQUARE_MARKS)
        ctx = MacroContext(executor, {})
        self._run('pallet_scan_4corners', ctx, pitch_x=140.0, pitch_y=200.0)
        result = self._run('pallet_capture_teach', ctx, slot='pick')
        self.assertTrue(result.ok, result.message)
        entry = ctx.get('teach_poses')['pick']
        self.assertIn('plane', entry)
        self.assertIn('absolute', entry)


class StopFlagTest(unittest.TestCase):
    """[정지] 뒤에도 마법사가 다시 돌아야 한다.

    JobExecutor._stop_requested 는 run_from() 계열에서만 꺼진다. 매크로를 레시피 밖에서
    직접 부르는 마법사는 그 경로를 안 지나므로, 한 번 정지하면 플래그가 남아 이후
    모든 매크로가 진입 즉시 «정지 요청으로 …중단» 으로 끝났다 (2026-08-24 실기).
    """

    def _run(self, macro, ctx, **params):
        from tm_task_manager.macros import run_macro
        return run_macro(macro, ctx, params)

    def test_stale_stop_flag_blocks_without_clear(self):
        """회귀 재현 — 지우지 않으면 막힌다."""
        executor = FakeExecutor(marks=SQUARE_MARKS)
        executor._stop_requested = True
        ctx = MacroContext(executor, {})
        result = self._run('pallet_scan_4corners', ctx, pitch_x=140.0, pitch_y=200.0)
        self.assertFalse(result.ok)
        self.assertIn('정지', result.message)

    def test_clear_stop_request_unblocks(self):
        executor = FakeExecutor(marks=SQUARE_MARKS)
        executor._stop_requested = True
        ctx = MacroContext(executor, {})
        ctx.clear_stop_request()
        self.assertFalse(ctx.is_stop_requested)
        result = self._run('pallet_scan_4corners', ctx, pitch_x=140.0, pitch_y=200.0)
        self.assertTrue(result.ok, result.message)

    def test_capture_marker_unblocks_too(self):
        executor = FakeExecutor()
        executor._marks = {None: {'x': 1.0, 'y': 2.0, 'z': 3.0,
                                  'rx': 180.0, 'ry': 0.0, 'rz': 30.0}}
        executor._stop_requested = True
        ctx = MacroContext(executor, {})
        ctx.clear_stop_request()
        result = self._run('pallet_capture_marker', ctx)
        self.assertTrue(result.ok, result.message)
        self.assertIn('position_marker_pose', ctx.blackboard)

    def test_tab_clears_flag_on_each_run(self):
        """탭이 매 실행 시작마다 지우는지 — 소스에 호출이 있어야 한다."""
        import inspect
        from tm_task_manager.tabs import pallet_teach_tab
        source = inspect.getsource(pallet_teach_tab.PalletTeachTab._run)
        self.assertIn('clear_stop_request', source,
                      '_run 이 시작 시 정지 플래그를 지우지 않습니다')


class CenterApproachTargetTest(unittest.TestCase):
    """중심 접근의 목표 좌표.

    (이전에 «PTP 대신 pose_keep 을 써야 한다» 는 가설로 테스트를 뒀으나, 실기에서
     같은 에러가 재현되어 가설이 기각됐다. 원인은 이동 방식이 아니라 **평면 법선
     방향**이었다 → PlaneNormalUpTest. 여기는 목표 좌표 계약만 남긴다.)
    """

    PLATE = {'x': 870.0, 'y': 200.0, 'z': -400.0, 'rx': 0.0, 'ry': 0.0, 'rz': 0.0}

    def _approach(self, executor, **params):
        from tm_task_manager.macros import run_macro
        ctx = MacroContext(executor, {'plate_pose': self.PLATE})
        return run_macro('pallet_center_approach', ctx, params), ctx

    def test_target_is_plane_center_plus_normal(self):
        ex = FakeExecutor()
        _, ctx = self._approach(ex, standoff_mm=150.0)
        target = ctx.get('approach_pose')
        self.assertAlmostEqual(target['x'], self.PLATE['x'], places=3)
        self.assertAlmostEqual(target['y'], self.PLATE['y'], places=3)
        self.assertAlmostEqual(target['z'], self.PLATE['z'] + 150.0, places=3)

    def test_reports_failure_when_move_rejected(self):
        ex = FakeExecutor()
        ex.move_ok = False
        result, _ = self._approach(ex, standoff_mm=150.0)
        self.assertFalse(result.ok)
        self.assertIn('중심 접근 이동 실패', result.message)


class PlaneNormalUpTest(unittest.TestCase):
    """팔레트 면은 늘 위를 본다 — 법선이 아래면 목표가 팔레트 속으로 들어간다.

    실측 2026-08-24: 팔레트가 90° 돌아 놓여 마크 감김이 뒤집히자 평면 rx -180.00 이
    나왔고, 목표 Z 가 평면 -150mm(팔레트 속)로 잡혀 TMflow 가 거부했다.
    """

    FLIPPED = {'x': 14.99, 'y': 909.23, 'z': -256.33,
               'rx': -180.00, 'ry': 0.12, 'rz': 176.43}   # 실측
    UPRIGHT = {'x': 546.875, 'y': -219.146, 'z': -325.564,
               'rx': 0.284, 'ry': -0.515, 'rz': 89.962}   # 실측 pallet5

    def _normal_z(self, plate):
        from tm_task_manager.tools.jig_plane_calculator import plane_normal_from_pose
        return float(plane_normal_from_pose(plate)[2])

    def test_flipped_is_turned_up(self):
        from tm_task_manager.macros.pallet_teach import normalize_plate_pose_up
        self.assertLess(self._normal_z(self.FLIPPED), 0, '픽스처가 뒤집힌 게 맞아야 한다')
        fixed = normalize_plate_pose_up(self.FLIPPED)
        self.assertGreater(self._normal_z(fixed), 0)

    def test_upright_is_untouched(self):
        from tm_task_manager.macros.pallet_teach import normalize_plate_pose_up
        fixed = normalize_plate_pose_up(self.UPRIGHT)
        for key in ('x', 'y', 'z', 'rx', 'ry', 'rz'):
            self.assertAlmostEqual(fixed[key], self.UPRIGHT[key], places=6)

    def test_position_never_changes(self):
        from tm_task_manager.macros.pallet_teach import normalize_plate_pose_up
        fixed = normalize_plate_pose_up(self.FLIPPED)
        for key in ('x', 'y', 'z'):
            self.assertEqual(fixed[key], self.FLIPPED[key])

    def test_stays_right_handed(self):
        import numpy as np
        from tm_task_manager.macros.pallet_teach import normalize_plate_pose_up
        from tm_task_manager.tools.jig_plane_calculator import _rotation_matrix_from_pose
        fixed = normalize_plate_pose_up(self.FLIPPED)
        self.assertAlmostEqual(np.linalg.det(_rotation_matrix_from_pose(fixed)), 1.0, places=6)

    def test_approach_target_is_above_plane(self):
        """실측 뒤집힌 평면에서도 목표가 평면 **위** 여야 한다."""
        from tm_task_manager.macros import run_macro
        from tm_task_manager.macros.pallet_teach import normalize_plate_pose_up
        ex = FakeExecutor(tcp=(0.36, 639.52, -252.51, 180.0, 0.0, 0.0))
        ctx = MacroContext(ex, {'plate_pose': normalize_plate_pose_up(self.FLIPPED)})
        result = run_macro('pallet_center_approach', ctx, {'standoff_mm': 150.0})
        self.assertTrue(result.ok, result.message)
        self.assertAlmostEqual(ctx.get('approach_pose')['z'],
                               self.FLIPPED['z'] + 150.0, places=2)

    def test_scan_normalizes_before_publishing(self):
        """스캔 매크로가 칠판에 올리기 전에 정규화하는지."""
        from tm_task_manager.macros import run_macro
        # jig 배치를 뒤집어 감김 방향을 반대로 만든다
        flipped_marks = {4: SQUARE_MARKS[1], 2: SQUARE_MARKS[3],
                         1: SQUARE_MARKS[4], 3: SQUARE_MARKS[2]}
        ex = FakeExecutor(marks=flipped_marks)
        ctx = MacroContext(ex, {})
        result = run_macro('pallet_scan_4corners', ctx,
                           {'pitch_x': 140.0, 'pitch_y': 200.0})
        self.assertTrue(result.ok, result.message)
        self.assertGreater(self._normal_z(ctx.get('plate_pose')), 0,
                           '칠판에 올라간 평면의 법선이 아래를 향합니다')


class RecipeGeneratorTest(unittest.TestCase):
    PLATE = {'x': 870.0, 'y': 200.0, 'z': -400.0, 'rx': 180.0, 'ry': 0.0, 'rz': 0.0}
    MARKER = {'x': 700.0, 'y': 400.0, 'z': -390.0, 'rx': 180.0, 'ry': 0.0, 'rz': 30.0}
    TEACH = {
        'pick': {'plane': {'x': 10.0, 'y': -20.0, 'z': 30.0,
                           'rx': 180.0, 'ry': 0.0, 'rz': 5.0},
                 'absolute': {'x': 880.0, 'y': 180.0, 'z': -370.0,
                              'rx': 180.0, 'ry': 0.0, 'rz': 5.0}},
        'place': {'plane': {'x': -10.0, 'y': 20.0, 'z': 30.0,
                            'rx': 180.0, 'ry': 0.0, 'rz': -5.0},
                  'absolute': {'x': 860.0, 'y': 220.0, 'z': -370.0,
                               'rx': 180.0, 'ry': 0.0, 'rz': -5.0}},
    }
    START = {'x': 800.0, 'y': 300.0, 'z': -200.0, 'rx': 180.0, 'ry': 0.0, 'rz': -90.0}

    def _generator(self, tmp):
        return PalletRecipeGenerator(recipe_dir=tmp, package_root=tmp)

    def _emit_fixed(self, tmp, **over):
        kwargs = dict(pallet_name='pallet9', mount='fixed', plate_pose=self.PLATE,
                      teach_poses=self.TEACH, scan_start_tcp=self.START,
                      pitch_x=140.0, pitch_y=200.0, operator='tester')
        kwargs.update(over)
        return self._generator(tmp).emit(**kwargs)

    def test_fixed_emits_three(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._emit_fixed(tmp)
            self.assertEqual(len(paths), 3)
            names = sorted(os.path.basename(p) for p in paths)
            self.assertEqual(names, ['pallet9_cali.yaml', 'pallet9_pick.yaml',
                                     'pallet9_place.yaml'])

    def test_fixed_cali_scans_four_corners(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._emit_fixed(tmp)
            cali = [p for p in paths if p.endswith('_cali.yaml')][0]
            with open(cali, encoding='utf-8') as handle:
                document = yaml.safe_load(handle)
            types = [job['type'] for job in document['jobs']]
            self.assertEqual(types.count('scan_tm_landmark_jig'), 4)
            self.assertEqual(types.count('move_linear'), 3)
            self.assertEqual(types[-1], 'calculate_plate_pose')

    MARKS = [
        {'jig_number': 1, 'x': 940.0, 'y': 100.0, 'z': -400.0,
         'rx': 180.0, 'ry': 0.0, 'rz': 0.0, 'detected': True},
        {'jig_number': 2, 'x': 940.0, 'y': 300.0, 'z': -400.0,
         'rx': 180.0, 'ry': 0.0, 'rz': 0.0, 'detected': True},
        {'jig_number': 3, 'x': 800.0, 'y': 100.0, 'z': -400.0,
         'rx': 180.0, 'ry': 0.0, 'rz': 0.0, 'detected': True},
        {'jig_number': 4, 'x': 800.0, 'y': 300.0, 'z': -400.0,
         'rx': 180.0, 'ry': 0.0, 'rz': 0.0, 'detected': True},
    ]

    def test_pick_starts_by_restoring_plane(self):
        """첫 잡이 load_plate_pose 여야 한다 — 없으면 «평면 pose 가 없습니다» 로 실패한다."""
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._emit_fixed(tmp)
            pick = [p for p in paths if p.endswith('_pick.yaml')][0]
            with open(pick, encoding='utf-8') as handle:
                document = yaml.safe_load(handle)
            # 검증본과 같이 recipe_info · 그리퍼 열기 · 대기 뒤에 온다
            loads = [j for j in document['jobs'] if j['type'] == 'load_plate_pose']
            self.assertEqual(len(loads), 1)
            moves = [i for i, j in enumerate(document['jobs'])
                     if j['type'] == 'move_to_plane_pose']
            load_index = document['jobs'].index(loads[0])
            self.assertLess(load_index, moves[0],
                            '평면 복원이 첫 이동보다 앞서야 한다')
            params = loads[0]['params']
            self.assertIn('pallet9', params['source_path'])
            self.assertEqual(params['file_prefix'], 'pallet9_teach')

    def test_snapshot_is_written_and_loadable(self):
        """스냅샷이 load_plate_pose 가 읽는 형식이어야 한다 (landmarks jig1~4)."""
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._emit_fixed(tmp, plate_marks=self.MARKS)
            snaps = [p for p in paths if 'plate_pose_calc' in p]
            self.assertEqual(len(snaps), 1, '평면 스냅샷이 하나 있어야 한다')
            with open(snaps[0], encoding='utf-8') as handle:
                snap = yaml.safe_load(handle)
            self.assertIn('landmarks', snap)
            self.assertEqual(sorted(snap['landmarks']),
                             ['jig1', 'jig2', 'jig3', 'jig4'])
            self.assertIn('plate_pose', snap)

            # 실행기와 같은 경로로 평균이 되는지 (jig1~4 완비 검사 통과)
            from tm_task_manager.tools.jig_plane_calculator import (
                average_landmarks_from_files)
            averaged, used, skipped = average_landmarks_from_files(snaps)
            self.assertEqual(len(used), 1, f'스냅샷이 건너뛰어졌습니다: {skipped}')
            self.assertIsNotNone(averaged)

    def test_snapshot_requires_four_marks(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                self._emit_fixed(tmp, plate_marks=self.MARKS[:3])

    # 기존 검증본 pallet5_pick.yaml / pallet5_place.yaml 의 잡 순서 (2026-08-19 실기 확정)
    # 상공 진입(+250) 이 맨 앞에 붙는다 — 낮은 높이로 옆에서 들어가지 않는다
    PICK_SHAPE = ['recipe_info', 'schunk_release', 'wait', 'load_plate_pose',
                  'move_to_plane_pose', 'move_to_plane_pose', 'move_to_plane_pose',
                  'schunk_grip', 'wait',
                  'move_to_plane_pose', 'move_to_plane_pose']
    PLACE_SHAPE = ['recipe_info', 'load_plate_pose',
                   'move_to_plane_pose', 'move_to_plane_pose', 'move_to_plane_pose',
                   'schunk_release', 'wait',
                   'move_to_plane_pose', 'move_to_plane_pose']

    def test_pick_shape_matches_verified_recipe(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._emit_fixed(tmp)
            pick = [p for p in paths if p.endswith('_pick.yaml')][0]
            document = yaml.safe_load(open(pick, encoding='utf-8'))
            self.assertEqual([j['type'] for j in document['jobs']], self.PICK_SHAPE)
            self.assertEqual([j['id'] for j in document['jobs']],
                             list(range(1, len(self.PICK_SHAPE) + 1)))

    def test_place_shape_matches_verified_recipe(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._emit_fixed(tmp)
            place = [p for p in paths if p.endswith('_place.yaml')][0]
            document = yaml.safe_load(open(place, encoding='utf-8'))
            self.assertEqual([j['type'] for j in document['jobs']], self.PLACE_SHAPE)

    def test_heights_match_verified_pattern(self):
        """파지면 → +20 접근 → +250 최종. 검증본이 쓰는 높이 패턴이다."""
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._emit_fixed(tmp)
            document = yaml.safe_load(
                open([p for p in paths if p.endswith('_pick.yaml')][0], encoding='utf-8'))
            moves = [j for j in document['jobs'] if j['type'] == 'move_to_plane_pose']
            self.assertEqual(len(moves), 5)
            grip_z = moves[2]['params']['offset_z']
            # 상공 진입(+250) → 접근(+20) → 파지(0) → 이탈(+20) → 이탈(+250)
            self.assertAlmostEqual(moves[0]['params']['offset_z'], grip_z + 250.0, places=3)
            self.assertAlmostEqual(moves[1]['params']['offset_z'], grip_z + 20.0, places=3)
            self.assertAlmostEqual(moves[3]['params']['offset_z'], grip_z + 20.0, places=3)
            self.assertAlmostEqual(moves[4]['params']['offset_z'], grip_z + 250.0, places=3)
            self.assertGreater(moves[0]['params']['offset_z'], moves[1]['params']['offset_z'],
                               '첫 진입이 접근보다 높아야 한다')

    def test_contact_move_params_match_verified(self):
        """접촉 구간은 3% + straight_path + decel_zone 0 — 검증본 그대로."""
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._emit_fixed(tmp)
            document = yaml.safe_load(
                open([p for p in paths if p.endswith('_pick.yaml')][0], encoding='utf-8'))
            moves = [j for j in document['jobs'] if j['type'] == 'move_to_plane_pose']
            contact = moves[2]['params']
            self.assertEqual(contact['velocity'], 3.0)
            self.assertTrue(contact['straight_path'])
            self.assertEqual(contact['decel_zone_mm'], 0.0)
            self.assertEqual(contact['max_radius_mm'], 200.0)
            self.assertEqual(contact['max_tilt_deg'], 30.0)
            # 접근 잡은 straight_path 를 켜지 않는다 (L자 경로)
            self.assertNotIn('straight_path', moves[0]['params'])
            self.assertEqual(moves[0]['params']['velocity'], 20.0)

    def test_gripper_jobs_carry_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._emit_fixed(tmp)
            document = yaml.safe_load(
                open([p for p in paths if p.endswith('_pick.yaml')][0], encoding='utf-8'))
            grips = [j for j in document['jobs'] if j['type'].startswith('schunk')]
            self.assertEqual([j['type'] for j in grips],
                             ['schunk_release', 'schunk_grip'])
            for j in grips:
                self.assertEqual(j['params']['timeout'], 15.0)
            waits = [j for j in document['jobs'] if j['type'] == 'wait']
            for j in waits:
                self.assertEqual(j['params']['duration'], 2000)

    def test_taught_pose_is_written_verbatim(self):
        """기본 발행은 티칭값을 **그대로** 쓴다 — 회전도 위치도 손대지 않는다.

        회전이 180/0/90 에서 벗어난 것은 오차가 아니라 사용자가 잡은 값이다
        (2026-08-24 사용자 확인). 임의 보정은 회귀로 간주한다.
        """
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._emit_fixed(tmp)
            document = yaml.safe_load(
                open([p for p in paths if p.endswith('_pick.yaml')][0], encoding='utf-8'))
            moves = [j for j in document['jobs'] if j['type'] == 'move_to_plane_pose']
            taught = self.TEACH['pick']['plane']
            for m in moves:
                q = m['params']
                for key in ('rx', 'ry', 'rz'):
                    self.assertAlmostEqual(q['offset_' + key], taught[key], places=3,
                                           msg=f'{key} 가 임의로 보정됐습니다')
                self.assertAlmostEqual(q['offset_x'], taught['x'], places=3)
                self.assertAlmostEqual(q['offset_y'], taught['y'], places=3)
            self.assertAlmostEqual(moves[2]['params']['offset_z'], taught['z'], places=3)

    def test_snap_is_opt_in_only(self):
        """스냅은 명시적으로 켤 때만 동작한다."""
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._emit_fixed(tmp, snap_rotation=True)
            document = yaml.safe_load(
                open([p for p in paths if p.endswith('_pick.yaml')][0], encoding='utf-8'))
            moves = [j for j in document['jobs'] if j['type'] == 'move_to_plane_pose']
            self.assertEqual(moves[1]['params']['offset_rx'], 180.0)

    def test_snap_picks_nearest_quarter_turn(self):
        from tm_task_manager.services.pallet_recipe_generator import snap_rotation_to_plane
        for raw, want in ((89.752, 90.0), (-90.008, -90.0), (0.31, 0.0),
                          (179.6, 180.0), (-179.267, -180.0)):
            out = snap_rotation_to_plane({'x': 1.0, 'y': 2.0, 'z': 3.0,
                                          'rx': -179.267, 'ry': -0.245, 'rz': raw})
            self.assertEqual(out['rz'], want, f'rz {raw} -> {out["rz"]} (기대 {want})')
            self.assertEqual(out['rx'], 180.0)
            self.assertEqual(out['ry'], 0.0)
            self.assertEqual((out['x'], out['y'], out['z']), (1.0, 2.0, 3.0),
                             '위치를 건드리면 안 된다')

    def test_floating_uses_landmark_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._generator(tmp).emit(
                pallet_name='pallet9', mount='floating', plate_pose=self.PLATE,
                teach_poses=self.TEACH, marker_pose=self.MARKER,
                marker_view_tcp=self.START, operator='tester')
            names = sorted(os.path.basename(p) for p in paths)
            self.assertEqual(names, ['pallet9_marker_scan.yaml', 'pallet9_pick.yaml',
                                     'pallet9_place.yaml'])
            pick = [p for p in paths if p.endswith('_pick.yaml')][0]
            with open(pick, encoding='utf-8') as handle:
                document = yaml.safe_load(handle)
            moves = [j for j in document['jobs'] if j['type'] == 'move_to_landmark_pose']
            # 상공진입 · 접근 · 접촉 · 근접이탈 · 최종이탈
            self.assertEqual(len(moves), 5)
            params = moves[2]['params']
            self.assertEqual(params['frame_mode'], 'rz_only')
            self.assertEqual(params['landmark_source'], 'file')
            self.assertEqual(params['file_prefix'], 'pallet9_marker_scan')
            self.assertGreater(params['max_age_min'], 0.0)

    def test_marker_scan_grips_before_shooting(self):
        """촬영 전 그리퍼를 **닫는다** — 열면 턱이 카메라 시야를 가린다."""
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._generator(tmp).emit(
                pallet_name='pallet9', mount='floating', plate_pose=self.PLATE,
                teach_poses=self.TEACH, marker_pose=self.MARKER,
                marker_view_tcp=self.START)
            scan = [p for p in paths if p.endswith('_marker_scan.yaml')][0]
            document = yaml.safe_load(open(scan, encoding='utf-8'))
            first = document['jobs'][0]
            self.assertEqual(first['type'], 'schunk_grip', '열면 안 되고 닫아야 한다')
            self.assertEqual(first['params']['timeout'], 15.0)
            self.assertNotIn('schunk_release',
                             [j['type'] for j in document['jobs']])

    def test_marker_scan_approaches_from_above(self):
        """촬영 자세로 직행하지 않고 상공 200mm 를 경유해 하강한다."""
        from tm_task_manager.services.pallet_recipe_generator import MARKER_VIEW_LIFT_MM
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._generator(tmp).emit(
                pallet_name='pallet9', mount='floating', plate_pose=self.PLATE,
                teach_poses=self.TEACH, marker_pose=self.MARKER,
                marker_view_tcp=self.START)
            scan = [p for p in paths if p.endswith('_marker_scan.yaml')][0]
            document = yaml.safe_load(open(scan, encoding='utf-8'))
            moves = [j for j in document['jobs'] if j['type'] == 'move_to_point']
            self.assertEqual(len(moves), 2, '상공 경유 + 하강 2구간이어야 한다')
            high, low = moves[0]['params'], moves[1]['params']
            self.assertAlmostEqual(high['Z'], self.START['z'] + MARKER_VIEW_LIFT_MM, places=3)
            self.assertAlmostEqual(low['Z'], self.START['z'], places=3)
            self.assertGreater(high['Z'], low['Z'], '상공이 더 높아야 한다')
            # XY·자세는 동일 — 수직 하강
            for key in ('X', 'Y', 'Rx', 'Ry', 'Rz'):
                self.assertAlmostEqual(high[key], low[key], places=3)
            # 스캔은 하강 뒤에
            types = [j['type'] for j in document['jobs']]
            self.assertLess(types.index('move_to_point'), types.index('scan_tm_landmark'))

    def test_landmark_radius_covers_every_job(self):
        """max_radius_mm 는 실행기와 **같은 3D 식**으로, 모든 잡을 덮어야 한다.

        실행기는 √(x²+y²+z²) 로 검사한다(job_executor.py:2231). 평면거리(x·y)만 보고
        상한을 잡으면 상승 구간에서 z 가 커져 오거부된다
        (2026-08-25 실기: 실제 487.20mm 인데 상한 420.30mm 로 발행 → 거부).
        """
        import math
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._generator(tmp).emit(
                pallet_name='pallet9', mount='floating', plate_pose=self.PLATE,
                teach_poses=self.TEACH, marker_pose=self.MARKER,
                marker_view_tcp=self.START)
            for path in [p for p in paths if p.endswith(('_pick.yaml', '_place.yaml'))]:
                document = yaml.safe_load(open(path, encoding='utf-8'))
                moves = [j for j in document['jobs']
                         if j['type'] == 'move_to_landmark_pose']
                self.assertTrue(moves)
                for j in moves:
                    q = j['params']
                    radius = math.sqrt(q['offset_x'] ** 2 + q['offset_y'] ** 2
                                       + q['offset_z'] ** 2)
                    self.assertLessEqual(
                        radius, q['max_radius_mm'],
                        f"{os.path.basename(path)} '{j.get('caption')}' 이 상한을 넘습니다 "
                        f"({radius:.2f} > {q['max_radius_mm']:.2f})")

    def test_floating_marker_scan_saves_pose(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._generator(tmp).emit(
                pallet_name='pallet9', mount='floating', plate_pose=self.PLATE,
                teach_poses=self.TEACH, marker_pose=self.MARKER,
                marker_view_tcp=self.START)
            scan = [p for p in paths if p.endswith('_marker_scan.yaml')][0]
            with open(scan, encoding='utf-8') as handle:
                document = yaml.safe_load(handle)
            types = [job['type'] for job in document['jobs']]
            self.assertIn('scan_tm_landmark', types)
            self.assertIn('save_landmark_pose', types)

    def test_floating_requires_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                self._generator(tmp).emit(
                    pallet_name='pallet9', mount='floating', plate_pose=self.PLATE,
                    teach_poses=self.TEACH)

    def test_rejects_path_traversal_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            for bad in ('../escape', 'a/b', '', '.hidden'):
                with self.assertRaises(ValueError, msg=f"'{bad}' 가 통과했습니다"):
                    self._emit_fixed(tmp, pallet_name=bad)

    def test_rejects_missing_teach(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                self._emit_fixed(tmp, teach_poses={'pick': self.TEACH['pick']})

    def test_overwrite_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._emit_fixed(tmp)
            with self.assertRaises(FileExistsError):
                self._emit_fixed(tmp)
            # overwrite=True 면 통과해야 한다
            self._emit_fixed(tmp, overwrite=True)


def _write_measurement(directory, name, marks, jitter=0.0):
    """`calculate_plate_pose` 가 남기는 것과 같은 모양의 측정 파일을 만든다."""
    landmarks = {}
    for index in range(1, 5):
        base = marks[index]
        landmarks[f'jig{index}'] = {
            'x': base['x'] + jitter, 'y': base['y'] + jitter, 'z': base['z'],
            'rx': base['rx'], 'ry': base['ry'], 'rz': base['rz'],
            'measured_at': '2026-08-24 10:00:00',
        }
    path = os.path.join(directory, name)
    with open(path, 'w', encoding='utf-8') as handle:
        yaml.safe_dump({'operator': 'tester', 'recipe': 'pallet0_cali',
                        'landmarks': landmarks}, handle, allow_unicode=True)
    return path


# jig 번호 기준 배치 (파일은 jig1~4 를 이름으로 갖는다)
FILE_MARKS = {
    1: {'x': 940.0, 'y': 100.0, 'z': -400.0, 'rx': 180.0, 'ry': 0.0, 'rz': 0.0},
    2: {'x': 940.0, 'y': 300.0, 'z': -400.0, 'rx': 180.0, 'ry': 0.0, 'rz': 0.0},
    3: {'x': 800.0, 'y': 100.0, 'z': -400.0, 'rx': 180.0, 'ry': 0.0, 'rz': 0.0},
    4: {'x': 800.0, 'y': 300.0, 'z': -400.0, 'rx': 180.0, 'ry': 0.0, 'rz': 0.0},
}


class LoadMeasurementsTest(unittest.TestCase):
    def _run(self, ctx, **params):
        from tm_task_manager.macros import run_macro
        return run_macro('pallet_load_measurements', ctx, params)

    def test_averages_multiple_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(4):
                _write_measurement(tmp, f'm{i}.yaml', FILE_MARKS, jitter=0.0)
            ctx = MacroContext(FakeExecutor(), {})
            result = self._run(ctx, source_path=tmp, outlier_method='none')
            self.assertTrue(result.ok, result.message)
            self.assertIn('plate_pose', ctx.blackboard)
            self.assertEqual(len(ctx.get('measurement_sources')), 4)
            plate = ctx.get('plate_pose')
            self.assertAlmostEqual(plate['x'], 870.0, places=3)
            self.assertAlmostEqual(plate['y'], 200.0, places=3)

    def test_outlier_file_is_rejected(self):
        """한 파일이 크게 튀면 iqr 이 걷어내 중심이 끌려가지 않아야 한다."""
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(6):
                _write_measurement(tmp, f'good{i}.yaml', FILE_MARKS, jitter=0.0)
            _write_measurement(tmp, 'bad.yaml', FILE_MARKS, jitter=50.0)

            ctx_none = MacroContext(FakeExecutor(), {})
            self._run(ctx_none, source_path=tmp, max_files=0, outlier_method='none')
            drifted = ctx_none.get('plate_pose')['x']

            ctx_iqr = MacroContext(FakeExecutor(), {})
            self._run(ctx_iqr, source_path=tmp, max_files=0, outlier_method='iqr')
            cleaned = ctx_iqr.get('plate_pose')['x']

            self.assertGreater(abs(drifted - 870.0), 1.0, '평균만 하면 끌려가야 정상')
            self.assertAlmostEqual(cleaned, 870.0, places=3)

    def test_missing_folder_reports(self):
        ctx = MacroContext(FakeExecutor(), {})
        result = self._run(ctx, source_path='/nonexistent/whatever')
        self.assertFalse(result.ok)
        self.assertIn('측정 파일을 찾지 못했습니다', result.message)

    def test_skips_incomplete_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_measurement(tmp, 'ok.yaml', FILE_MARKS)
            with open(os.path.join(tmp, 'partial.yaml'), 'w', encoding='utf-8') as handle:
                yaml.safe_dump({'landmarks': {'jig1': FILE_MARKS[1]}}, handle)
            ctx = MacroContext(FakeExecutor(), {})
            result = self._run(ctx, source_path=tmp, max_files=0, outlier_method='none')
            self.assertTrue(result.ok, result.message)
            self.assertEqual(len(ctx.get('measurement_sources')), 1)

    def test_explicit_file_paths_win(self):
        with tempfile.TemporaryDirectory() as tmp:
            chosen = _write_measurement(tmp, 'a.yaml', FILE_MARKS)
            _write_measurement(tmp, 'b.yaml', FILE_MARKS)
            _write_measurement(tmp, 'c.yaml', FILE_MARKS)
            ctx = MacroContext(FakeExecutor(), {})
            result = self._run(ctx, source_path=tmp, file_paths=[chosen],
                               outlier_method='none')
            self.assertTrue(result.ok, result.message)
            self.assertEqual(ctx.get('measurement_sources'), [chosen])

    def test_clears_scan_start_tcp(self):
        """이 경로에는 실측 시작 자세가 없다 — 남아 있으면 엉뚱한 cali 가 발행된다."""
        with tempfile.TemporaryDirectory() as tmp:
            _write_measurement(tmp, 'a.yaml', FILE_MARKS)
            ctx = MacroContext(FakeExecutor(), {'scan_start_tcp': {'x': 1.0}})
            self._run(ctx, source_path=tmp, outlier_method='none')
            self.assertNotIn('scan_start_tcp', ctx.blackboard)

    def test_sequence_from_files_is_valid(self):
        ok, problems = validate_sequence(
            ['pallet_load_measurements', 'pallet_center_approach',
             'pallet_capture_teach', 'pallet_emit_recipes'])
        self.assertTrue(ok, f"파일 경로 순서가 검증에 실패했습니다: {problems}")


class FileRouteEmitTest(unittest.TestCase):
    """저장된 측정으로 만든 평면은 cali 를 새로 발행하지 않는다."""

    def test_fixed_without_start_pose_emits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = PalletRecipeGenerator(recipe_dir=tmp, package_root=tmp).emit(
                pallet_name='pallet9', mount='fixed',
                plate_pose=RecipeGeneratorTest.PLATE,
                teach_poses=RecipeGeneratorTest.TEACH,
                scan_start_tcp=None, operator='tester')
            names = sorted(os.path.basename(p) for p in paths)
            self.assertEqual(names, ['pallet9_pick.yaml', 'pallet9_place.yaml'])

    def test_fixed_with_start_pose_still_emits_cali(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = PalletRecipeGenerator(recipe_dir=tmp, package_root=tmp).emit(
                pallet_name='pallet9', mount='fixed',
                plate_pose=RecipeGeneratorTest.PLATE,
                teach_poses=RecipeGeneratorTest.TEACH,
                scan_start_tcp=RecipeGeneratorTest.START,
                pitch_x=140.0, pitch_y=200.0, operator='tester')
            self.assertEqual(len(paths), 3)


class CenterApproachAlignmentTest(unittest.TestCase):
    """중심 접근 자세 — 공구 면이 평면과 평행하고 회전이 팔레트를 따라야 한다."""

    # 일부러 기울인 평면 (Rx 3°, Ry -2°) + 회전 40°
    TILTED = {'x': 870.0, 'y': 200.0, 'z': -400.0, 'rx': 3.0, 'ry': -2.0, 'rz': 40.0}

    def _approach(self, mode):
        from tm_task_manager.macros import run_macro
        executor = FakeExecutor(tcp=(500.0, 0.0, 0.0, 180.0, 0.0, -90.0))
        ctx = MacroContext(executor, {'plate_pose': self.TILTED})
        result = run_macro('pallet_center_approach', ctx,
                           {'standoff_mm': 150.0, 'rz_mode': mode})
        self.assertTrue(result.ok, result.message)
        return ctx.get('approach_pose')

    @staticmethod
    def _tool_z_vs_normal(pose, plate):
        import numpy as np
        from tm_task_manager.tools.jig_plane_calculator import (
            _rotation_matrix_from_pose, plane_normal_from_pose)
        tool_z = _rotation_matrix_from_pose(pose)[:, 2]
        normal = plane_normal_from_pose(plate)
        cos = abs(float(np.dot(tool_z, normal)))
        return math.degrees(math.acos(min(1.0, cos)))

    def test_default_is_pallet_aligned(self):
        """기본값이 plane 이어야 한다 — 티칭 시작 자세가 팔레트에 맞춰져 있어야 한다."""
        self.assertEqual(MACROS['pallet_center_approach'].defaults()['rz_mode'], 'plane')

    def test_tool_face_parallel_to_plane_in_both_modes(self):
        # 허용오차 1e-3 deg — acos 는 인자가 1 에 가까울수록 조건수가 나빠 정확히
        # 0 이 안 나온다(실측 잔차 1.2e-06 deg). 기계적으로는 완전 일치다.
        for mode in ('plane', 'keep'):
            with self.subTest(mode=mode):
                pose = self._approach(mode)
                angle = self._tool_z_vs_normal(pose, self.TILTED)
                self.assertLess(angle, 1e-3,
                                f'공구 Z 가 평면 법선과 {angle:.6f}° 어긋났습니다 — '
                                '면이 평행하지 않습니다')

    def test_plane_mode_follows_pallet_rotation(self):
        pose = self._approach('plane')
        # 평면 Y축(긴 변) 정렬 = 평면 Rz + 90
        expected = self.TILTED['rz'] + 90.0
        delta = abs((pose['rz'] - expected + 180.0) % 360.0 - 180.0)
        self.assertLess(delta, 0.5, f"Rz {pose['rz']:.3f} 이 팔레트 회전을 안 따랐습니다")

    def test_keep_mode_holds_current_rotation(self):
        pose = self._approach('keep')
        delta = abs((pose['rz'] - (-90.0) + 180.0) % 360.0 - 180.0)
        self.assertLess(delta, 0.5, 'keep 은 현재 공구 회전을 유지해야 한다')

    def test_tilt_is_followed_not_flat(self):
        """기울어진 평면이면 Rx/Ry 가 180/0 에 머물지 않아야 한다."""
        pose = self._approach('plane')
        flat = abs(abs(pose['rx']) - 180.0) < 0.05 and abs(pose['ry']) < 0.05
        self.assertFalse(flat, '기울기를 따라가지 않고 수평 자세로 갔습니다')


class RecipeDirResolutionTest(unittest.TestCase):
    """레시피 저장 위치 — 반드시 **소스** 트리여야 한다.

    colcon 이 build/ 에 소스 심링크를 걸어 두므로, `__file__` 을 심링크 해석 없이
    거슬러 올라가면 build/ 가 나온다. 그러면 저장한 레시피가 소스에 안 남고 다음
    빌드에 사라진다 (2026-08-24 실사고).
    """

    def test_default_root_matches_paths_ssot(self):
        from tm_task_manager import paths
        generator = PalletRecipeGenerator()
        self.assertEqual(generator.package_root, str(paths.PACKAGE_ROOT))

    def test_default_root_is_not_build_dir(self):
        generator = PalletRecipeGenerator()
        parts = generator.package_root.replace(os.sep, '/').split('/')
        self.assertNotIn('build', parts,
                         f'레시피가 빌드 디렉토리에 저장됩니다: {generator.recipe_dir}')

    def test_default_root_is_symlink_resolved(self):
        generator = PalletRecipeGenerator()
        self.assertEqual(os.path.realpath(generator.package_root),
                         generator.package_root,
                         '심링크가 풀리지 않았습니다')


class TabWiringTest(unittest.TestCase):
    """탭 배선 검증 — 위젯 키 오타·시그널 연결 누락은 실행해 봐야만 드러난다.

    화면 없이(offscreen) 실제 위젯을 만들어 버튼 핸들러를 호출한다. PyQt5 가 없으면
    건너뛴다(테스트 환경 차이로 전체 스위트를 깨지 않는다).
    """

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        try:
            from PyQt5.QtWidgets import QApplication
        except ImportError as exc:                       # pragma: no cover
            raise unittest.SkipTest(f"PyQt5 없음: {exc}")
        cls.app = QApplication.instance() or QApplication([])

    def _make_tab(self):
        from PyQt5.QtWidgets import QTabWidget, QWidget
        from tm_task_manager.tabs import PalletTeachTab

        class FakeMainWindow(QWidget):
            def __init__(self):
                super().__init__()
                self.tabWidget_main = QTabWidget(self)
                self.ros_node = None
                self.recipe_manager = None
                self.job_executor = None
                self.vision_manager = None
                self.gv_manager = None
                self.config_manager = None
                self.logs = []

            def _log(self, message, kind=None):
                self.logs.append(message)

        window = FakeMainWindow()
        tab = PalletTeachTab(window)
        tab.init_ui()
        return window, tab

    def test_tab_is_added(self):
        window, _ = self._make_tab()
        self.assertEqual(window.tabWidget_main.count(), 1)
        self.assertEqual(window.tabWidget_main.tabText(0), '팔레트 티칭')

    def test_tab_is_not_appended_last_when_bar_is_full(self):
        """탭바가 이미 꽉 찼을 때 끝에 붙이면 스크롤 뒤로 숨는다 — 앞쪽에 끼워야 한다.

        실기에서 «탭이 안 생겼다» 로 보인 원인이 이것이었다(기존 탭 15개, 우리 것이 16번째).
        """
        from PyQt5.QtWidgets import QTabWidget, QWidget
        from tm_task_manager.tabs import PalletTeachTab
        from tm_task_manager.tabs.pallet_teach_tab import TAB_INSERT_INDEX

        class FakeMainWindow(QWidget):
            def __init__(self):
                super().__init__()
                self.tabWidget_main = QTabWidget(self)
                for i in range(15):                      # main_window.ui 의 기존 탭 수
                    self.tabWidget_main.addTab(QWidget(), f'기존{i}')
                self.ros_node = None
                self.recipe_manager = None
                self.job_executor = None
                self.vision_manager = None
                self.gv_manager = None
                self.config_manager = None
                self.logs = []

            def _log(self, message, kind=None):
                self.logs.append(message)

        window = FakeMainWindow()
        tab = PalletTeachTab(window)
        tab.init_ui()

        bar = window.tabWidget_main
        self.assertEqual(bar.count(), 16)
        index = bar.indexOf(tab.ui_widget)
        self.assertEqual(index, TAB_INSERT_INDEX)
        self.assertLess(index, bar.count() - 1,
                        '맨 끝에 붙으면 탭바 스크롤 뒤로 숨는다')
        self.assertEqual(bar.tabText(index), '팔레트 티칭')

    def test_file_list_is_multi_select(self):
        from PyQt5.QtWidgets import QAbstractItemView
        _, tab = self._make_tab()
        self.assertEqual(tab._widgets['src_files'].selectionMode(),
                         QAbstractItemView.ExtendedSelection,
                         '드래그·Shift 다중 선택이 되어야 한다')

    def test_list_roundtrip_and_remove(self):
        _, tab = self._make_tab()
        with tempfile.TemporaryDirectory() as tmp:
            paths = [_write_measurement(tmp, f'm{i}.yaml', FILE_MARKS) for i in range(3)]
            tab._set_listed_paths(paths)
            self.assertEqual(tab._listed_paths(), paths)

            tab._widgets['src_files'].item(0).setSelected(True)
            tab._on_remove_selected_files()
            self.assertEqual(tab._listed_paths(), paths[1:])

            tab._on_clear_files()
            self.assertEqual(tab._listed_paths(), [])

    def test_handlers_exist_for_every_button(self):
        """버튼마다 연결된 핸들러가 실제로 있는지 — 이름 오타를 잡는다."""
        _, tab = self._make_tab()
        for key in ('src_pick_files', 'src_pick_folder', 'src_clear', 'src_remove',
                    'src_apply', 'scan_button', 'approach_button', 'pick_button',
                    'place_button', 'emit_button', 'marker_button'):
            self.assertIn(key, tab._widgets, f'{key} 위젯이 없습니다')


if __name__ == '__main__':
    unittest.main()
