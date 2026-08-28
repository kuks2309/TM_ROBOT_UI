# -*- coding: utf-8 -*-
"""로봇 IP 이중 시도 — MK2·MK4 둘 다 두드려 응답하는 쪽을 쓴다.

틀리면 **엉뚱한 로봇에 명령이 간다.** 그래서 순서와 «응답 없을 때 아무거나 고르지
않는다» 를 명시적으로 검사한다.
"""
import os
import socket
import sys
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tm_task_manager import robot_profile as rp  # noqa: E402

MK2_IP = '192.168.192.127'
MK4_IP = '169.254.122.16'


class PortConstantTest(unittest.TestCase):

    def test_port_is_sct_command_channel(self):
        """5890 = SCT(명령/Listen). 5891(상태)만 살아도 로봇을 못 움직인다."""
        self.assertEqual(rp.ROBOT_PORT, 5890)

    def test_timeout_is_short(self):
        """링크로컬 무응답이 기동을 오래 붙들면 안 된다 — 두 개 합쳐 2초 이내."""
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
        """확정된 프로필이 앞이어야 한다 — 두 로봇이 같은 망이면 순서가 곧 안전이다."""
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
        # 127.0.0.1 의 임의 포트를 열었다 닫아 «확실히 닫힌» 포트를 만든다
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
        """둘 다 응답하면 확정된 프로필 쪽을 쓴다 — 오접속이 사고이기 때문."""
        os.environ[rp.ENV_VAR] = 'mk2'
        with mock.patch.object(rp, 'reachable', lambda *a, **k: True):
            self.assertEqual(rp.probe_robot_ip()[0], 'mk2')
        os.environ[rp.ENV_VAR] = 'mk4'
        with mock.patch.object(rp, 'reachable', lambda *a, **k: True):
            self.assertEqual(rp.probe_robot_ip()[0], 'mk4')

    def test_nothing_answers_returns_none(self):
        """응답이 없으면 아무거나 고르지 않는다 — 호출자가 기본값을 정한다."""
        with mock.patch.object(rp, 'reachable', lambda *a, **k: False):
            self.assertEqual(rp.probe_robot_ip(), (None, None))

    def test_probe_report_lists_both(self):
        with mock.patch.object(rp, 'reachable', lambda *a, **k: False):
            text = rp.probe_report()
        self.assertIn('mk2', text)
        self.assertIn('mk4', text)
        self.assertIn('무응답', text)

    def test_detect_id_uses_probe_as_last_resort(self):
        """앞 단서가 모두 없을 때만 로봇 응답으로 판정한다."""
        with mock.patch.object(rp, 'local_ipv4', lambda: []):
            def only_mk4(ip, port=rp.ROBOT_PORT, timeout_sec=1.0):
                return ip == MK4_IP
            with mock.patch.object(rp, 'reachable', only_mk4):
                self.assertEqual(rp.detect_id(), 'mk4')

    def test_no_infinite_recursion(self):
        """detect_id → probe → candidate → detect_id 재귀가 없어야 한다."""
        with mock.patch.object(rp, 'local_ipv4', lambda: []):
            with mock.patch.object(rp, 'reachable', lambda *a, **k: False):
                self.assertIsNone(rp.detect_id())   # 재귀면 RecursionError 로 죽는다


if __name__ == '__main__':
    unittest.main()
