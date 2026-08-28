# -*- coding: utf-8 -*-
"""그리퍼 백엔드 — 기종에 따라 레시피가 올바른 잡 타입으로 나오는지.

MK2 는 SCHUNK(`schunk_*`), MK4 는 SMC(`smc_*`) 를 쓴다. 실행기는 두 계열을 모두
지원하므로 갈리는 곳은 **발행 시점** 하나다. 여기서 검사하는 것:

  1) 고른 기종의 잡만 나오고 반대편 잡은 **한 개도** 섞이지 않는다
  2) 기본값은 SCHUNK — 기존 레시피·테스트와의 호환이 깨지지 않는다
  3) 감지 순서는 SMC → SCHUNK (GripperOverrideService 규약과 같아야 한다)
  4) 확인이 안 되면 **거부**한다 — 추측해서 반대편 잡을 로봇에 올리지 않는다
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tm_task_manager.hardware import gripper as gripper_mod  # noqa: E402
from tm_task_manager.hardware.gripper import (  # noqa: E402
    ABSENT, BUILT, LIVE, NoGripperDetected, SCHUNK, SMC, detect, probe, resolve,
)
from tm_task_manager.services.pallet_recipe_generator import (  # noqa: E402
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
    """레시피 3개를 내고 (경로들, 등장한 잡 타입 집합) 을 준다."""
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
    """고른 기종의 잡만 나오는가."""

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
        """기본값이 바뀌면 기존 레시피·테스트가 조용히 깨진다."""
        with tempfile.TemporaryDirectory() as tmp:
            _, types = _emit(tmp)
        self.assertIn('schunk_grip', types)
        self.assertEqual([t for t in types if t.startswith('smc_')], [])

    def test_backend_object_accepted(self):
        """문자열 대신 백엔드 객체를 그대로 넘겨도 된다 (매크로가 쓰는 경로)."""
        with tempfile.TemporaryDirectory() as tmp:
            _, types = _emit(tmp, gripper=SMC)
        self.assertIn('smc_grip', types)

    def test_grip_and_release_counts_match_between_backends(self):
        """기종만 바뀌고 잡 구성은 동일해야 한다 — 경로가 달라지면 안 된다."""
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
        """GripperOverrideService 와 같은 순서여야 한다 — 바뀌면 기본 선택이 뒤집힌다."""
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
        """노드가 안 떠 있는 그리퍼를 고르면 실행 시점에 실패한다 — 고르지 않는다."""
        with mock.patch.object(gripper_mod, 'probe', lambda b, n, t=3.0: BUILT):
            self.assertIsNone(detect(object()))


class ResolveTest(unittest.TestCase):

    def test_explicit_wins_over_detection(self):
        """사용자가 화면에서 고른 값이 감지보다 우선한다."""
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
