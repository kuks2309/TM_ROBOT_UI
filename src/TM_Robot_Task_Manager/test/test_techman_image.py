# -*- coding: utf-8 -*-
import os
import sys
import threading
import time
import unittest
from unittest import mock
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tm_task_manager.services.image_frame_cache import (
    ERR_STOPPED,
    ImageFrameCache,
)


class LatestFrameCacheTest(unittest.TestCase):

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
        cache = ImageFrameCache()
        baseline = cache.baseline()
        cache.push('the-shot')
        frame, err = cache.wait_after(baseline, timeout_sec=0.5)
        self.assertIsNone(err)
        self.assertEqual(frame, 'the-shot')


class FreshnessTest(unittest.TestCase):

    def test_stale_frame_before_baseline_is_rejected(self):
        cache = ImageFrameCache()
        cache.push('old-frame')
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
        cache = ImageFrameCache()
        baseline = cache.baseline()
        calls = []
        cache.wait_after(baseline, timeout_sec=0.15,
                         on_poll=lambda: calls.append(1))
        self.assertGreater(len(calls), 0, 'on_poll 이 호출되지 않았습니다')


class TwoConsumerTest(unittest.TestCase):

    def test_each_consumer_gets_frame_after_its_own_baseline(self):
        cache = ImageFrameCache()
        a = cache.baseline()
        cache.push('for-A')
        b = cache.baseline()
        cache.push('for-B')

        frame_a, err_a = cache.wait_after(a, timeout_sec=0.5)
        frame_b, err_b = cache.wait_after(b, timeout_sec=0.5)
        self.assertIsNone(err_a)
        self.assertIsNone(err_b)
        self.assertEqual(frame_a, 'for-A')
        self.assertEqual(frame_b, 'for-B')

    def test_second_request_does_not_erase_first_result(self):
        cache = ImageFrameCache()
        a = cache.baseline()
        cache.push('for-A')
        cache.baseline()
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
        cache = ImageFrameCache()
        threads = [threading.Thread(target=lambda: [cache.push('f') for _ in range(50)])
                   for _ in range(4)]
        for th in threads:
            th.start()
        for th in threads:
            th.join(10.0)
        self.assertEqual(cache.baseline(), 200)


class WiringTest(unittest.TestCase):

    def _src(self, path):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(base, 'tm_task_manager', path), encoding='utf-8') as f:
            return f.read()

    def test_callback_always_pushes(self):
        src = self._src('main_window.py')
        self.assertIn('self.techman_image_cache.push(msg)', src,
                      '콜백이 캐시에 밀어넣지 않습니다')

    def test_consumers_use_baseline(self):
        for path in ('services/image_capture_service.py', 'job_executor.py',
                     'services/image_processing_service.py'):
            src = self._src(path)
            self.assertIn('baseline = ', src, '%s 가 baseline 을 받지 않습니다' % path)
            self.assertIn('wait_techman_image(', src,
                          '%s 가 새 대기 API 를 쓰지 않습니다' % path)


class ImwriteReturnTest(unittest.TestCase):

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
