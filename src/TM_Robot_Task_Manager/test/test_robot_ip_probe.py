# -*- coding: utf-8 -*-
import os
import socket
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tm_task_manager import robot_profile as rp

MK2_IP = '192.168.192.127'
MK4_IP = '169.254.122.16'


class PortConstantTest(unittest.TestCase):

    def test_port_is_sct_command_channel(self):
        self.assertEqual(rp.ROBOT_PORT, 5890)

    def test_timeout_is_short(self):
        self.assertLessEqual(rp.PROBE_TIMEOUT_SEC, 1.0)


class CandidateOrderTest(unittest.TestCase):

    def setUp(self):
        self._saved = os.environ.pop(rp.ENV_VAR, None)

    def tearDown(self):
        os.environ.pop(rp.ENV_VAR, None)
        if self._saved is not None:
            os.environ[rp.ENV_VAR] = self._saved

    def test_both_robots_are_candidates(self):
        pairs = rp.candidate_robot_ips()
        self.assertEqual(sorted(p[0] for p in pairs), ['mk2', 'mk4'])
        ips = dict(pairs)
        self.assertEqual(ips['mk2'], MK2_IP)
        self.assertEqual(ips['mk4'], MK4_IP)

    def test_fixed_profile_goes_first(self):
        os.environ[rp.ENV_VAR] = 'mk4'
        self.assertEqual(rp.candidate_robot_ips()[0][0], 'mk4')
        os.environ[rp.ENV_VAR] = 'mk2'
        self.assertEqual(rp.candidate_robot_ips()[0][0], 'mk2')

    def test_no_duplicates(self):
        os.environ[rp.ENV_VAR] = 'mk2'
        ids = [p[0] for p in rp.candidate_robot_ips()]
        self.assertEqual(len(ids), len(set(ids)))


class ReachableTest(unittest.TestCase):

    def test_closed_port_is_not_reachable(self):
        s = socket.socket()
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
        s.close()
        self.assertFalse(rp.reachable('127.0.0.1', port, 0.3))

    def test_open_port_is_reachable(self):
        server = socket.socket()
        server.bind(('127.0.0.1', 0))
        server.listen(1)
        port = server.getsockname()[1]
        stop = threading.Event()

        def accept_loop():
            server.settimeout(0.5)
            while not stop.is_set():
                try:
                    conn, _ = server.accept()
                    conn.close()
                except Exception:
                    pass

        thread = threading.Thread(target=accept_loop, daemon=True)
        thread.start()
        try:
            self.assertTrue(rp.reachable('127.0.0.1', port, 1.0))
        finally:
            stop.set()
            server.close()

    def test_bad_host_does_not_raise(self):
        self.assertFalse(rp.reachable('", 잘못된 호스트', 5890, 0.2))


class ProbeTest(unittest.TestCase):

    def setUp(self):
        self._saved = os.environ.pop(rp.ENV_VAR, None)

    def tearDown(self):
        os.environ.pop(rp.ENV_VAR, None)
        if self._saved is not None:
            os.environ[rp.ENV_VAR] = self._saved

    def test_picks_the_one_that_answers(self):
        def only_mk4(ip, port=rp.ROBOT_PORT, timeout_sec=1.0):
            return ip == MK4_IP
        with mock.patch.object(rp, 'reachable', only_mk4):
            robot_id, ip = rp.probe_robot_ip()
        self.assertEqual((robot_id, ip), ('mk4', MK4_IP))

    def test_picks_mk2_when_mk2_answers(self):
        def only_mk2(ip, port=rp.ROBOT_PORT, timeout_sec=1.0):
            return ip == MK2_IP
        with mock.patch.object(rp, 'reachable', only_mk2):
            robot_id, ip = rp.probe_robot_ip()
        self.assertEqual((robot_id, ip), ('mk2', MK2_IP))

    def test_fixed_profile_wins_when_both_answer(self):
        os.environ[rp.ENV_VAR] = 'mk2'
        with mock.patch.object(rp, 'reachable', lambda *a, **k: True):
            self.assertEqual(rp.probe_robot_ip()[0], 'mk2')
        os.environ[rp.ENV_VAR] = 'mk4'
        with mock.patch.object(rp, 'reachable', lambda *a, **k: True):
            self.assertEqual(rp.probe_robot_ip()[0], 'mk4')

    def test_nothing_answers_returns_none(self):
        with mock.patch.object(rp, 'reachable', lambda *a, **k: False):
            self.assertEqual(rp.probe_robot_ip(), (None, None))

    def test_probe_report_lists_both(self):
        with mock.patch.object(rp, 'reachable', lambda *a, **k: False):
            text = rp.probe_report()
        self.assertIn('mk2', text)
        self.assertIn('mk4', text)
        self.assertIn('무응답', text)

    def test_detect_id_uses_probe_as_last_resort(self):
        with mock.patch.object(rp, 'local_ipv4', lambda: []):
            def only_mk4(ip, port=rp.ROBOT_PORT, timeout_sec=1.0):
                return ip == MK4_IP
            with mock.patch.object(rp, 'reachable', only_mk4):
                self.assertEqual(rp.detect_id(), 'mk4')

    def test_no_infinite_recursion(self):
        # 실 config 의 active.txt·프로필 존재와 무관해야 하므로 빈 임시 디렉터리로 격리
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(rp, '_robots_dir', lambda: tmp):
                with mock.patch.object(rp, 'local_ipv4', lambda: []):
                    with mock.patch.object(rp, 'reachable', lambda *a, **k: False):
                        self.assertIsNone(rp.detect_id())


if __name__ == '__main__':
    unittest.main()
