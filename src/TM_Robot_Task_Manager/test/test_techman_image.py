# -*- coding: utf-8 -*-
"""TMflow 이미지 수신 — «찍어도 UI 에 안 뜬다» 의 원인 4가지를 막는다.

현장 증상(2026-08-27 사용자 보고): 캡처를 눌러도 화면에 이미지가 안 나타나는 일이 잦다.
코드에서 확인된 원인과, 여기서 검사하는 것:

  ① 대기 시작 **전**에 도착한 프레임을 버렸다  → 항상 캐시하고 일련번호로 고른다
  ② 이번 요청의 이미지인지 검증이 없었다        → baseline 보다 뒤엣것만 채택
  ③ 소비자 3곳이 상태 1칸을 공유했다            → 소비자마다 자기 baseline
  ④ cv2.imwrite 반환값을 안 봤다                → 실패를 실패로 보고

①②③ 은 ROS 를 모르는 ImageFrameCache 를 직접 검사한다 — 로봇도 rclpy 도 필요 없다.
"""
import os
import sys
import threading
import time
import unittest
from unittest import mock
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tm_task_manager.services.image_frame_cache import (  # noqa: E402
    ERR_STOPPED,
    ImageFrameCache,
)


class LatestFrameCacheTest(unittest.TestCase):
    """① 대기 중이 아니어도 프레임이 보존되는가."""

    def test_frame_is_kept_even_with_no_waiter(self):
        cache = ImageFrameCache()
        cache.push('frame-A')
        frame, seq, at = cache.peek()
        self.assertEqual(frame, 'frame-A')
        self.assertEqual(seq, 1)
        self.assertGreater(at, 0.0)

    def test_sequence_increases_per_frame(self):
        cache = ImageFrameCache()
        for i in range(1, 4):
            self.assertEqual(cache.push('frame-%d' % i), i)

    def test_frame_between_command_and_wait_is_not_lost(self):
        """증상의 핵심: 촬영 명령 직후·대기 진입 직전에 온 프레임.

        예전 구현은 이 프레임을 버려 타임아웃까지 기다리다 실패했다.
        """
        cache = ImageFrameCache()
        baseline = cache.baseline()
        cache.push('the-shot')                 # 대기 루프에 들어가기 전에 도착
        frame, err = cache.wait_after(baseline, timeout_sec=0.5)
        self.assertIsNone(err)
        self.assertEqual(frame, 'the-shot')


class FreshnessTest(unittest.TestCase):
    """② 이번 요청의 것인지 일련번호로 가리는가."""

    def test_stale_frame_before_baseline_is_rejected(self):
        cache = ImageFrameCache()
        cache.push('old-frame')                # 이전 캡처의 늦은 프레임
        baseline = cache.baseline()
        frame, err = cache.wait_after(baseline, timeout_sec=0.3)
        self.assertIsNone(frame, '요청 이전 프레임을 이번 사진으로 썼습니다')
        self.assertIn('타임아웃', err)

    def test_new_frame_after_stale_one_is_accepted(self):
        cache = ImageFrameCache()
        cache.push('old-frame')
        baseline = cache.baseline()
        cache.push('new-frame')
        frame, err = cache.wait_after(baseline, timeout_sec=0.5)
        self.assertIsNone(err)
        self.assertEqual(frame, 'new-frame')

    def test_take_after_does_not_block(self):
        cache = ImageFrameCache()
        baseline = cache.baseline()
        self.assertIsNone(cache.take_after(baseline))
        cache.push('x')
        self.assertEqual(cache.take_after(baseline), 'x')

    def test_timeout_reports_reason_and_is_prompt(self):
        cache = ImageFrameCache()
        baseline = cache.baseline()
        start = time.monotonic()
        frame, err = cache.wait_after(baseline, timeout_sec=0.2)
        self.assertIsNone(frame)
        self.assertIn('타임아웃', err)
        self.assertLess(time.monotonic() - start, 2.0, '타임아웃이 제때 나지 않습니다')

    def test_should_stop_aborts(self):
        cache = ImageFrameCache()
        baseline = cache.baseline()
        frame, err = cache.wait_after(
            baseline, timeout_sec=5.0, should_stop=lambda: True)
        self.assertIsNone(frame)
        self.assertEqual(err, ERR_STOPPED)

    def test_on_poll_is_called(self):
        """자체 실행기가 없는 호출부가 spin 을 돌릴 수 있어야 한다."""
        cache = ImageFrameCache()
        baseline = cache.baseline()
        calls = []
        cache.wait_after(baseline, timeout_sec=0.15,
                         on_poll=lambda: calls.append(1))
        self.assertGreater(len(calls), 0, 'on_poll 이 호출되지 않았습니다')


class TwoConsumerTest(unittest.TestCase):
    """③ 두 소비자가 서로의 이미지를 가져가거나 지우지 않는가."""

    def test_each_consumer_gets_frame_after_its_own_baseline(self):
        cache = ImageFrameCache()
        a = cache.baseline()                   # 소비자 A 요청
        cache.push('for-A')
        b = cache.baseline()                   # 소비자 B 요청 (A 이후)
        cache.push('for-B')

        frame_a, err_a = cache.wait_after(a, timeout_sec=0.5)
        frame_b, err_b = cache.wait_after(b, timeout_sec=0.5)
        self.assertIsNone(err_a)
        self.assertIsNone(err_b)
        self.assertEqual(frame_a, 'for-A')
        self.assertEqual(frame_b, 'for-B')

    def test_second_request_does_not_erase_first_result(self):
        """예전에는 B 의 요청이 current_techman_image 를 None 으로 밀었다."""
        cache = ImageFrameCache()
        a = cache.baseline()
        cache.push('for-A')
        cache.baseline()                       # B 가 끼어든다
        frame_a, err_a = cache.wait_after(a, timeout_sec=0.5)
        self.assertIsNone(err_a, 'B 의 요청이 A 의 결과를 지웠습니다')
        self.assertEqual(frame_a, 'for-A')

    def test_concurrent_waiters_each_get_a_frame(self):
        cache = ImageFrameCache()
        a = cache.baseline()
        results = {}

        def waiter(key, baseline):
            results[key] = cache.wait_after(baseline, timeout_sec=3.0)

        t1 = threading.Thread(target=waiter, args=('a', a))
        t1.start()
        time.sleep(0.1)
        b = cache.baseline()
        t2 = threading.Thread(target=waiter, args=('b', b))
        t2.start()
        time.sleep(0.1)
        cache.push('shared')
        t1.join(5.0)
        t2.join(5.0)
        self.assertEqual(results['a'], ('shared', None))
        self.assertEqual(results['b'], ('shared', None))

    def test_many_pushes_are_counted_under_threads(self):
        """락이 실제로 잠기는가 — 번호가 새거나 겹치면 안 된다."""
        cache = ImageFrameCache()
        threads = [threading.Thread(target=lambda: [cache.push('f') for _ in range(50)])
                   for _ in range(4)]
        for th in threads:
            th.start()
        for th in threads:
            th.join(10.0)
        self.assertEqual(cache.baseline(), 200)


class WiringTest(unittest.TestCase):
    """노드가 캐시를 실제로 쓰도록 배선됐는가 (소스 확인)."""

    def _src(self, path):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(base, 'tm_task_manager', path), encoding='utf-8') as f:
            return f.read()

    def test_callback_always_pushes(self):
        src = self._src('main_window.py')
        self.assertIn('self.techman_image_cache.push(msg)', src,
                      '콜백이 캐시에 밀어넣지 않습니다')

    def test_consumers_use_baseline(self):
        """세 소비자가 모두 자기 baseline 을 받아 쓰는가."""
        for path in ('services/image_capture_service.py', 'job_executor.py',
                     'services/image_processing_service.py'):
            src = self._src(path)
            self.assertIn('baseline = ', src, '%s 가 baseline 을 받지 않습니다' % path)
            self.assertIn('wait_techman_image(', src,
                          '%s 가 새 대기 API 를 쓰지 않습니다' % path)


class ImwriteReturnTest(unittest.TestCase):
    """④ 저장 실패가 성공으로 보고되지 않는가."""

    def _src(self, path):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(base, 'tm_task_manager', path), encoding='utf-8') as f:
            return f.read()

    def test_main_window_checks_imwrite(self):
        self.assertIn('if not cv2.imwrite(', self._src('main_window.py'),
                      '_save_captured_image 가 imwrite 반환값을 확인하지 않습니다')

    def test_processing_service_checks_imwrite(self):
        self.assertIn('if not cv2.imwrite(',
                      self._src('services/image_processing_service.py'),
                      'save_image 가 imwrite 반환값을 확인하지 않습니다')

    def test_save_image_returns_false_when_imwrite_fails(self):
        from tm_task_manager.services import image_processing_service as svc
        service = svc.ImageProcessingService.__new__(svc.ImageProcessingService)
        service.processed_image = object()
        service.processing_error = MagicMock()
        with mock.patch.object(svc.cv2, 'imwrite', return_value=False):
            self.assertFalse(service.save_image('/nowhere/x.png'))
        service.processing_error.emit.assert_called()

    def test_save_image_returns_true_when_imwrite_succeeds(self):
        from tm_task_manager.services import image_processing_service as svc
        service = svc.ImageProcessingService.__new__(svc.ImageProcessingService)
        service.processed_image = object()
        service.processing_error = MagicMock()
        with mock.patch.object(svc.cv2, 'imwrite', return_value=True):
            self.assertTrue(service.save_image('/tmp/x.png'))


if __name__ == '__main__':
    unittest.main()
