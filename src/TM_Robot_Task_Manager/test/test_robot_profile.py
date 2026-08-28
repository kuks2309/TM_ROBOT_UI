# -*- coding: utf-8 -*-
"""로봇 프로필 — 기계마다 갈리는 값이 정확히 갈리는지, 못 정할 땐 멈추는지.

이 프로필이 틀리면 반대편 기계의 IP 로 로봇을 움직이거나 반대편 그리퍼 잡을
발행한다. 그래서 «못 정하면 None» 을 명시적으로 검사한다.
"""
import os
import sys
import unittest

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tm_task_manager import paths  # noqa: E402
from tm_task_manager import robot_profile as rp  # noqa: E402


class ProfileFileTest(unittest.TestCase):

    def test_robots_dir_exists(self):
        self.assertTrue(paths.ROBOTS_DIR.is_dir(),
                        'config/robots 가 없습니다: %s' % paths.ROBOTS_DIR)

    def test_both_robots_available(self):
        self.assertEqual(sorted(rp.available()), ['mk2', 'mk4'])

    def test_mk2_values(self):
        p = rp.load('mk2')
        self.assertEqual(p['robot_ip'], '192.168.192.127')
        self.assertEqual(p['gripper']['id'], 'schunk')
        # MK2 는 완료 검증 센서가 없다 — 이 값이 뒤집히면 화면 보증이 거짓이 된다
        self.assertFalse(p['gripper']['verifies_completion'])

    def test_mk4_values(self):
        p = rp.load('mk4')
        self.assertEqual(p['robot_ip'], '169.254.122.16')
        self.assertEqual(p['gripper']['id'], 'smc')
        self.assertTrue(p['gripper']['verifies_completion'])

    def test_two_robots_do_not_share_an_ip(self):
        """식별용 IP 가 겹치면 자동 판정이 뒤집힌다."""
        a = set(rp.load('mk2')['identify']['ips'])
        b = set(rp.load('mk4')['identify']['ips'])
        self.assertEqual(a & b, set(), 'MK2·MK4 식별 IP 가 겹칩니다: %s' % (a & b))

    def test_gripper_ids_match_backend_registry(self):
        """프로필이 부르는 기종명이 hardware.gripper 에 실제로 있어야 한다."""
        from tm_task_manager.hardware.gripper import BACKENDS
        for robot_id in rp.available():
            gid = rp.load(robot_id)['gripper']['id']
            self.assertIn(gid, BACKENDS, '%s 의 그리퍼 %s 가 등록돼 있지 않습니다' % (robot_id, gid))

    def test_unknown_profile_raises(self):
        with self.assertRaises(rp.ProfileError):
            rp.load('mk9')


class DetectionTest(unittest.TestCase):

    def setUp(self):
        self._saved = os.environ.pop(rp.ENV_VAR, None)

    def tearDown(self):
        os.environ.pop(rp.ENV_VAR, None)
        if self._saved is not None:
            os.environ[rp.ENV_VAR] = self._saved

    def test_env_var_wins(self):
        os.environ[rp.ENV_VAR] = 'mk4'
        self.assertEqual(rp.detect_id(), 'mk4')
        self.assertEqual(rp.robot_ip(), '169.254.122.16')
        self.assertEqual(rp.gripper_id(), 'smc')

    def test_env_var_switches_cleanly(self):
        os.environ[rp.ENV_VAR] = 'mk2'
        self.assertEqual(rp.robot_ip(), '192.168.192.127')
        self.assertEqual(rp.gripper_id(), 'schunk')

    def test_active_file_used_when_no_env(self):
        marker = paths.ROBOTS_DIR / rp.ACTIVE_FILE
        existed = marker.exists()
        previous = marker.read_text(encoding='utf-8') if existed else None
        try:
            marker.write_text('mk4\n', encoding='utf-8')
            self.assertEqual(rp.detect_id(), 'mk4')
        finally:
            if previous is None:
                marker.unlink(missing_ok=True)
            else:
                marker.write_text(previous, encoding='utf-8')

    def test_robot_ip_falls_back_when_unresolved(self):
        """프로필을 못 정하면 호출자가 준 기본값을 그대로 돌려준다 — 지어내지 않는다."""
        marker = paths.ROBOTS_DIR / rp.ACTIVE_FILE
        existed = marker.exists()
        previous = marker.read_text(encoding='utf-8') if existed else None
        try:
            if existed:
                marker.unlink()
            # 이 기계(개발 PC)의 IP 는 어느 프로필에도 없으므로 미확정이어야 한다
            if rp.detect_id() is None:
                self.assertEqual(rp.robot_ip('9.9.9.9'), '9.9.9.9')
                self.assertIsNone(rp.active())
                with self.assertRaises(rp.ProfileError):
                    rp.active(required=True)
        finally:
            if previous is not None:
                marker.write_text(previous, encoding='utf-8')

    def test_describe_is_one_line(self):
        os.environ[rp.ENV_VAR] = 'mk2'
        text = rp.describe()
        self.assertIn('mk2', text)
        self.assertNotIn('\n', text)


class YamlShapeTest(unittest.TestCase):
    """필수 키가 빠지면 기동 시점이 아니라 여기서 걸린다."""

    REQUIRED = ('id', 'label', 'robot_ip', 'gripper', 'identify')

    def test_required_keys(self):
        for robot_id in rp.available():
            with open(rp.load(robot_id)['_path'], encoding='utf-8') as f:
                data = yaml.safe_load(f)
            for key in self.REQUIRED:
                self.assertIn(key, data, '%s 에 %s 가 없습니다' % (robot_id, key))
            self.assertIn('id', data['gripper'])
            self.assertIn('ips', data['identify'])
            self.assertTrue(data['identify']['ips'], '%s 식별 IP 가 비었습니다' % robot_id)


if __name__ == '__main__':
    unittest.main()
