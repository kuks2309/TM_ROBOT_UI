# -*- coding: utf-8 -*-
"""hardware/gripper 백엔드 선택(smc/schunk 탐지·명시 지정)과 레시피의 그리퍼 job 방출을 검증한다."""
import os
import sys
import tempfile
import unittest
from unittest import mock

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tm_task_manager.hardware import gripper as gripper_mod
from tm_task_manager.hardware.gripper import (
    ABSENT, BUILT, LIVE, NoGripperDetected, SCHUNK, SMC, detect, probe, resolve,
)
from tm_task_manager.services.pallet_recipe_generator import (
    PalletRecipeGenerator,
)


PLATE = {'x': 870.0, 'y': 200.0, 'z': -400.0, 'rx': 180.0, 'ry': 0.0, 'rz': 0.0}
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


def _emit(tmp, **over):
    kwargs = dict(recipe_dir=tmp, package_root=tmp)
    kwargs.update({k: v for k, v in over.items() if k == 'gripper'})
    generator = PalletRecipeGenerator(**kwargs)
    paths = generator.emit(pallet_name='pallet9', mount='fixed', plate_pose=PLATE,
                           teach_poses=TEACH, scan_start_tcp=START,
                           pitch_x=140.0, pitch_y=200.0, operator='tester')
    types = set()
    for path in paths:
        with open(path, encoding='utf-8') as f:
            doc = yaml.safe_load(f)
        for job in (doc.get('jobs') or []):
            types.add(job.get('type'))
    return paths, types


class JobTypeTest(unittest.TestCase):

    def test_schunk_emits_only_schunk(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, types = _emit(tmp, gripper='schunk')
        self.assertIn('schunk_grip', types)
        self.assertIn('schunk_release', types)
        self.assertEqual([t for t in types if t.startswith('smc_')], [],
                         'SCHUNK 을 골랐는데 SMC 잡이 섞였습니다')

    def test_smc_emits_only_smc(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, types = _emit(tmp, gripper='smc')
        self.assertIn('smc_grip', types)
        self.assertIn('smc_release', types)
        self.assertEqual([t for t in types if t.startswith('schunk_')], [],
                         'SMC 를 골랐는데 SCHUNK 잡이 섞였습니다')

    def test_default_stays_schunk(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, types = _emit(tmp)
        self.assertIn('schunk_grip', types)
        self.assertEqual([t for t in types if t.startswith('smc_')], [])

    def test_backend_object_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, types = _emit(tmp, gripper=SMC)
        self.assertIn('smc_grip', types)

    def test_grip_and_release_counts_match_between_backends(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths_a, _ = _emit(tmp, gripper='schunk')
            docs_a = [yaml.safe_load(open(p, encoding='utf-8')) for p in paths_a]
        with tempfile.TemporaryDirectory() as tmp:
            paths_b, _ = _emit(tmp, gripper='smc')
            docs_b = [yaml.safe_load(open(p, encoding='utf-8')) for p in paths_b]
        self.assertEqual(len(paths_a), len(paths_b))
        for a, b in zip(docs_a, docs_b):
            ja, jb = a.get('jobs') or [], b.get('jobs') or []
            self.assertEqual(len(ja), len(jb), '잡 개수가 기종에 따라 달라집니다')
            self.assertEqual([j['id'] for j in ja], [j['id'] for j in jb])


class BackendMappingTest(unittest.TestCase):

    def test_job_type_mapping(self):
        self.assertEqual(SMC.job_type(True), 'smc_grip')
        self.assertEqual(SMC.job_type(False), 'smc_release')
        self.assertEqual(SCHUNK.job_type(True), 'schunk_grip')
        self.assertEqual(SCHUNK.job_type(False), 'schunk_release')

    def test_detection_order_is_smc_then_schunk(self):
        self.assertEqual([b.id for b in gripper_mod.ORDER], ['smc', 'schunk'])


class ProbeTest(unittest.TestCase):

    def test_probe_absent_without_node(self):
        self.assertEqual(probe(SMC, None), ABSENT)
        self.assertEqual(probe(SCHUNK, None), ABSENT)

    def test_probe_absent_when_attribute_missing(self):
        self.assertEqual(probe(SMC, object()), ABSENT)

    def test_detect_prefers_smc_when_both_live(self):
        with mock.patch.object(gripper_mod, 'probe', lambda b, n, t=3.0: LIVE):
            self.assertIs(detect(object()), SMC)

    def test_detect_falls_back_to_schunk(self):
        def fake(backend, node, timeout_sec=3.0):
            return ABSENT if backend is SMC else LIVE
        with mock.patch.object(gripper_mod, 'probe', fake):
            self.assertIs(detect(object()), SCHUNK)

    def test_detect_ignores_built_but_not_live(self):
        with mock.patch.object(gripper_mod, 'probe', lambda b, n, t=3.0: BUILT):
            self.assertIsNone(detect(object()))


class ResolveTest(unittest.TestCase):

    def test_explicit_wins_over_detection(self):
        with mock.patch.object(gripper_mod, 'probe', lambda b, n, t=3.0: LIVE):
            self.assertIs(resolve('schunk', object()), SCHUNK)

    def test_explicit_without_node(self):
        self.assertIs(resolve('smc', None), SMC)
        self.assertIs(resolve('SCHUNK', None), SCHUNK)

    def test_unknown_name_refused(self):
        with self.assertRaises(NoGripperDetected):
            resolve('robotiq', None)

    def test_refuses_when_nothing_detected(self):
        with self.assertRaises(NoGripperDetected):
            resolve('', None)

    def test_refusal_message_names_both_backends(self):
        try:
            resolve('', None)
        except NoGripperDetected as exc:
            text = str(exc)
        self.assertIn('SMC', text)
        self.assertIn('SCHUNK', text)


if __name__ == '__main__':
    unittest.main()
