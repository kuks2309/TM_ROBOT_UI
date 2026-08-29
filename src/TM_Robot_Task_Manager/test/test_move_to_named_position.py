import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tm_task_manager.job_executor import JobExecutor
from tm_task_manager.recipe_manager import Job, RecipeManager
from tm_task_manager.services.config_manager import ConfigManager

POSITIONS_YAML = """
positions:
  home:
    description: joint home
    type: joint
    values: [0.0, -30.0, 120.0, 0.0, 90.0, 0.0]
  tcp_pick_palette:
    description: tcp pose
    type: tcp
    values: [-840.92, -0.16, 512.3, 90.0, -22.0, -90.0]
  broken:
    type: tcp
    values: [1.0, 2.0]
"""


def make_config(tmpdir: str) -> ConfigManager:
    path = os.path.join(tmpdir, 'positions.yaml')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(POSITIONS_YAML)
    return ConfigManager(config_path=path)


class TestNamedPositionConfig(unittest.TestCase):

    def test_get_position_returns_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            cm = make_config(tmp)
            entry = cm.get_position('tcp_pick_palette')
            self.assertEqual(entry['type'], 'tcp')
            self.assertEqual(len(entry['values']), 6)

    def test_get_position_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            cm = make_config(tmp)
            self.assertIsNone(cm.get_position('없는이름'))

    def test_get_position_names_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            cm = make_config(tmp)
            self.assertEqual(cm.get_position_names(),
                             ['broken', 'home', 'tcp_pick_palette'])


class TestMoveToNamedPositionJob(unittest.TestCase):

    def setUp(self):
        self.executor = JobExecutor(ros_node=mock.MagicMock())
        self.executor._move_to_position = mock.MagicMock(
            return_value=(True, "이동 완료"))
        self.logs = []
        self.executor.on_log = self.logs.append

    def _run(self, params):
        job = Job(job_id=1, job_type='move_to_named_position', params=params)
        return self.executor._exec_move_to_named_position(job)

    def _with_config(self, fn):
        with tempfile.TemporaryDirectory() as tmp:
            cm = make_config(tmp)
            with mock.patch(
                    'tm_task_manager.services.config_manager.ConfigManager',
                    return_value=cm):
                return fn()

    def test_job_type_registered(self):
        self.assertIn('move_to_named_position', RecipeManager.JOB_TYPES)
        self.assertEqual(
            RecipeManager.JOB_TYPES['move_to_named_position']['category'],
            'Motion')

    def test_tcp_entry_moves_ptp_t(self):
        ok = self._with_config(
            lambda: self._run({'name': 'tcp_pick_palette', 'velocity': 15.0}))
        self.assertTrue(ok)
        args = self.executor._move_to_position.call_args.args
        self.assertEqual(args[0], 'tcp')
        self.assertEqual(list(args[1:7]),
                         [-840.92, -0.16, 512.3, 90.0, -22.0, -90.0])
        self.assertEqual(args[7], 15.0)

    def test_joint_entry_moves_ptp_j(self):
        ok = self._with_config(lambda: self._run({'name': 'home'}))
        self.assertTrue(ok)
        args = self.executor._move_to_position.call_args.args
        self.assertEqual(args[0], 'joint')
        self.assertEqual(list(args[1:7]),
                         [0.0, -30.0, 120.0, 0.0, 90.0, 0.0])

    def test_missing_name_rejected(self):
        ok = self._with_config(lambda: self._run({'name': ''}))
        self.assertFalse(ok)
        self.executor._move_to_position.assert_not_called()

    def test_unknown_name_rejected(self):
        ok = self._with_config(lambda: self._run({'name': '없는이름'}))
        self.assertFalse(ok)
        self.executor._move_to_position.assert_not_called()

    def test_short_values_rejected(self):
        ok = self._with_config(lambda: self._run({'name': 'broken'}))
        self.assertFalse(ok)
        self.executor._move_to_position.assert_not_called()


if __name__ == '__main__':
    unittest.main()
