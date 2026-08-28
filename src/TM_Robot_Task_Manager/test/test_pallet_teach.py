import math
import os
import sys
import tempfile
import unittest

import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tm_task_manager.macros import MACROS, validate_sequence
from tm_task_manager.macros.base import MacroContext
from tm_task_manager.macros.pallet_teach import DEFAULT_CORNER_PLAN
from tm_task_manager.services.pallet_recipe_generator import (
    CORNER_PLAN,
    PalletRecipeGenerator,
)


class FakeNode:
    def __init__(self, tcp):
        self.current_tcp_pose = list(tcp)


class FakeExecutor:

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
        ok, problems = validate_sequence(
            ['pallet_center_approach', 'pallet_scan_4corners'])
        self.assertFalse(ok)
        self.assertTrue(any('plate_pose' in p for p in problems), problems)

    def test_corner_plan_matches_generator(self):
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

    def _run(self, macro, ctx, **params):
        from tm_task_manager.macros import run_macro
        return run_macro(macro, ctx, params)

    def test_stale_stop_flag_blocks_without_clear(self):
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
        import inspect
        from tm_task_manager.tabs import pallet_teach_tab
        source = inspect.getsource(pallet_teach_tab.PalletTeachTab._run)
        self.assertIn('clear_stop_request', source,
                      '_run 이 시작 시 정지 플래그를 지우지 않습니다')


class CenterApproachTargetTest(unittest.TestCase):

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

    FLIPPED = {'x': 14.99, 'y': 909.23, 'z': -256.33,
               'rx': -180.00, 'ry': 0.12, 'rz': 176.43}
    UPRIGHT = {'x': 546.875, 'y': -219.146, 'z': -325.564,
               'rx': 0.284, 'ry': -0.515, 'rz': 89.962}

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
        from tm_task_manager.macros import run_macro
        from tm_task_manager.macros.pallet_teach import normalize_plate_pose_up
        ex = FakeExecutor(tcp=(0.36, 639.52, -252.51, 180.0, 0.0, 0.0))
        ctx = MacroContext(ex, {'plate_pose': normalize_plate_pose_up(self.FLIPPED)})
        result = run_macro('pallet_center_approach', ctx, {'standoff_mm': 150.0})
        self.assertTrue(result.ok, result.message)
        self.assertAlmostEqual(ctx.get('approach_pose')['z'],
                               self.FLIPPED['z'] + 150.0, places=2)

    def test_scan_normalizes_before_publishing(self):
        from tm_task_manager.macros import run_macro
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
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._emit_fixed(tmp)
            pick = [p for p in paths if p.endswith('_pick.yaml')][0]
            with open(pick, encoding='utf-8') as handle:
                document = yaml.safe_load(handle)
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

            from tm_task_manager.tools.jig_plane_calculator import (
                average_landmarks_from_files)
            averaged, used, skipped = average_landmarks_from_files(snaps)
            self.assertEqual(len(used), 1, f'스냅샷이 건너뛰어졌습니다: {skipped}')
            self.assertIsNotNone(averaged)

    def test_snapshot_requires_four_marks(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                self._emit_fixed(tmp, plate_marks=self.MARKS[:3])

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
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._emit_fixed(tmp)
            document = yaml.safe_load(
                open([p for p in paths if p.endswith('_pick.yaml')][0], encoding='utf-8'))
            moves = [j for j in document['jobs'] if j['type'] == 'move_to_plane_pose']
            self.assertEqual(len(moves), 5)
            grip_z = moves[2]['params']['offset_z']
            self.assertAlmostEqual(moves[0]['params']['offset_z'], grip_z + 250.0, places=3)
            self.assertAlmostEqual(moves[1]['params']['offset_z'], grip_z + 20.0, places=3)
            self.assertAlmostEqual(moves[3]['params']['offset_z'], grip_z + 20.0, places=3)
            self.assertAlmostEqual(moves[4]['params']['offset_z'], grip_z + 250.0, places=3)
            self.assertGreater(moves[0]['params']['offset_z'], moves[1]['params']['offset_z'],
                               '첫 진입이 접근보다 높아야 한다')

    def test_contact_move_params_match_verified(self):
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
            self.assertEqual(len(moves), 5)
            params = moves[2]['params']
            self.assertEqual(params['frame_mode'], 'rz_only')
            self.assertEqual(params['landmark_source'], 'file')
            self.assertEqual(params['file_prefix'], 'pallet9_marker_scan')
            self.assertGreater(params['max_age_min'], 0.0)

    def test_marker_scan_grips_before_shooting(self):
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
            for key in ('X', 'Y', 'Rx', 'Ry', 'Rz'):
                self.assertAlmostEqual(high[key], low[key], places=3)
            types = [j['type'] for j in document['jobs']]
            self.assertLess(types.index('move_to_point'), types.index('scan_tm_landmark'))

    def test_landmark_radius_covers_every_job(self):
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
            self._emit_fixed(tmp, overwrite=True)


def _write_measurement(directory, name, marks, jitter=0.0):
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
        self.assertEqual(MACROS['pallet_center_approach'].defaults()['rz_mode'], 'plane')

    def test_tool_face_parallel_to_plane_in_both_modes(self):
        for mode in ('plane', 'keep'):
            with self.subTest(mode=mode):
                pose = self._approach(mode)
                angle = self._tool_z_vs_normal(pose, self.TILTED)
                self.assertLess(angle, 1e-3,
                                f'공구 Z 가 평면 법선과 {angle:.6f}° 어긋났습니다 — '
                                '면이 평행하지 않습니다')

    def test_plane_mode_follows_pallet_rotation(self):
        pose = self._approach('plane')
        expected = self.TILTED['rz'] + 90.0
        delta = abs((pose['rz'] - expected + 180.0) % 360.0 - 180.0)
        self.assertLess(delta, 0.5, f"Rz {pose['rz']:.3f} 이 팔레트 회전을 안 따랐습니다")

    def test_keep_mode_holds_current_rotation(self):
        pose = self._approach('keep')
        delta = abs((pose['rz'] - (-90.0) + 180.0) % 360.0 - 180.0)
        self.assertLess(delta, 0.5, 'keep 은 현재 공구 회전을 유지해야 한다')

    def test_tilt_is_followed_not_flat(self):
        pose = self._approach('plane')
        flat = abs(abs(pose['rx']) - 180.0) < 0.05 and abs(pose['ry']) < 0.05
        self.assertFalse(flat, '기울기를 따라가지 않고 수평 자세로 갔습니다')


class RecipeDirResolutionTest(unittest.TestCase):

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

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        try:
            from PyQt5.QtWidgets import QApplication
        except ImportError as exc:
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
        from PyQt5.QtWidgets import QTabWidget, QWidget
        from tm_task_manager.tabs import PalletTeachTab
        from tm_task_manager.tabs.pallet_teach_tab import TAB_INSERT_INDEX

        class FakeMainWindow(QWidget):
            def __init__(self):
                super().__init__()
                self.tabWidget_main = QTabWidget(self)
                for i in range(15):
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
        _, tab = self._make_tab()
        for key in ('src_pick_files', 'src_pick_folder', 'src_clear', 'src_remove',
                    'src_apply', 'scan_button', 'approach_button', 'pick_button',
                    'place_button', 'emit_button', 'marker_button'):
            self.assertIn(key, tab._widgets, f'{key} 위젯이 없습니다')


if __name__ == '__main__':
    unittest.main()
