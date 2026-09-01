# -*- coding: utf-8 -*-
"""pallet_recipe_generator 의 하강 모드(평면 법선/tcp_linear) 분기를 검증한다."""
import os
import sys
import tempfile
import unittest

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tm_task_manager.services.pallet_recipe_generator import (
    APPROACH_LIFT_MM,
    CLEAR_LIFT_MM,
    DESCENT_PLANE_NORMAL,
    DESCENT_TCP_LINEAR,
    PalletRecipeGenerator,
    TCP_CONTACT_VELOCITY_MMS,
    TCP_TRAVEL_VELOCITY_MMS,
)

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
VIEW = {'x': 750.0, 'y': 350.0, 'z': -150.0, 'rx': 180.0, 'ry': 0.0, 'rz': 0.0}


def _emit(tmp, mount='fixed', **over):
    kwargs = {k: v for k, v in over.items() if k in ('gripper', 'descent')}
    generator = PalletRecipeGenerator(recipe_dir=tmp, package_root=tmp, **kwargs)
    call = dict(pallet_name='pallet9', mount=mount, plate_pose=PLATE,
                teach_poses=TEACH, pitch_x=140.0, pitch_y=200.0, operator='tester')
    if mount == 'fixed':
        call['scan_start_tcp'] = START
    else:
        call['marker_pose'] = MARKER
        call['marker_view_tcp'] = VIEW
    return generator.emit(**call)


def _jobs(path):
    with open(path, encoding='utf-8') as f:
        return (yaml.safe_load(f) or {}).get('jobs') or []


def _pick(paths):
    return [p for p in paths if p.endswith('_pick.yaml')][0]


class PlaneMountTest(unittest.TestCase):

    def test_default_is_plane_normal(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs = _jobs(_pick(_emit(tmp)))
        types = {j['type'] for j in jobs}
        self.assertIn('move_to_plane_pose', types)
        self.assertNotIn('move_linear', types, '기본값이 TCP 리니어로 바뀌었습니다')

    def test_tcp_linear_replaces_final_segments(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs = _jobs(_pick(_emit(tmp, descent=DESCENT_TCP_LINEAR)))
        linear = [j for j in jobs if j['type'] == 'move_linear']
        plane = [j for j in jobs if j['type'] == 'move_to_plane_pose']
        self.assertEqual(len(linear), 3, '공구축 직선 잡이 3개여야 합니다')
        self.assertEqual(len(plane), 2, '상공 진입·접근은 평면 이동으로 남아야 합니다')

    def test_tcp_linear_signs_and_distances(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs = _jobs(_pick(_emit(tmp, descent=DESCENT_TCP_LINEAR)))
        linear = [j for j in jobs if j['type'] == 'move_linear']
        dz = [j['params']['offset Z'] for j in linear]
        vel = [j['params']['velocity'] for j in linear]
        self.assertEqual(dz, [APPROACH_LIFT_MM,
                              -APPROACH_LIFT_MM,
                              -(CLEAR_LIFT_MM - APPROACH_LIFT_MM)])
        self.assertEqual(dz, [20.0, -20.0, -230.0], '실기본(+20/-20/-230)과 다릅니다')
        self.assertEqual(vel, [TCP_CONTACT_VELOCITY_MMS,
                               TCP_CONTACT_VELOCITY_MMS,
                               TCP_TRAVEL_VELOCITY_MMS])
        self.assertEqual(vel, [10.0, 10.0, 50.0], '실기본(10/10/50 mm/s)과 다릅니다')

    def test_param_keys_have_spaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs = _jobs(_pick(_emit(tmp, descent=DESCENT_TCP_LINEAR)))
        params = [j['params'] for j in jobs if j['type'] == 'move_linear'][0]
        for key in ('offset X', 'offset Y', 'offset Z', 'velocity'):
            self.assertIn(key, params)

    def test_job_count_unchanged_between_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = _jobs(_pick(_emit(tmp, descent=DESCENT_PLANE_NORMAL)))
        with tempfile.TemporaryDirectory() as tmp:
            b = _jobs(_pick(_emit(tmp, descent=DESCENT_TCP_LINEAR)))
        self.assertEqual(len(a), len(b))
        self.assertEqual([j['id'] for j in a], [j['id'] for j in b])

    def test_gripper_jobs_survive_mode_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs = _jobs(_pick(_emit(tmp, descent=DESCENT_TCP_LINEAR, gripper='smc')))
        types = [j['type'] for j in jobs]
        self.assertIn('smc_grip', types)
        self.assertIn('smc_release', types)


class LandmarkMountTest(unittest.TestCase):

    def test_default_is_landmark_move(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs = _jobs(_pick(_emit(tmp, mount='floating')))
        types = {j['type'] for j in jobs}
        self.assertIn('move_to_landmark_pose', types)
        self.assertNotIn('move_linear', types)

    def test_tcp_linear_replaces_final_segments(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs = _jobs(_pick(_emit(tmp, mount='floating', descent=DESCENT_TCP_LINEAR)))
        linear = [j for j in jobs if j['type'] == 'move_linear']
        landmark = [j for j in jobs if j['type'] == 'move_to_landmark_pose']
        self.assertEqual(len(linear), 3)
        self.assertEqual(len(landmark), 2)
        dz = [j['params']['offset Z'] for j in linear]
        self.assertEqual(dz, [20.0, -20.0, -230.0])

    def test_place_side_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _emit(tmp, mount='floating', descent=DESCENT_TCP_LINEAR)
            place = [p for p in paths if p.endswith('_place.yaml')][0]
            jobs = _jobs(place)
        dz = [j['params']['offset Z'] for j in jobs if j['type'] == 'move_linear']
        self.assertEqual(dz, [20.0, -20.0, -230.0])


class ValidationTest(unittest.TestCase):

    def test_unknown_mode_refused(self):
        with self.assertRaises(ValueError):
            PalletRecipeGenerator(descent='diagonal')

    def test_case_and_space_tolerated(self):
        gen = PalletRecipeGenerator(descent='  TCP_Linear ')
        self.assertEqual(gen.descent, DESCENT_TCP_LINEAR)

    def test_empty_falls_back_to_default(self):
        self.assertEqual(PalletRecipeGenerator(descent='').descent,
                         DESCENT_PLANE_NORMAL)


if __name__ == '__main__':
    unittest.main()
