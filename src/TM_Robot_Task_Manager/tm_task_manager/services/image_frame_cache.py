# -*- coding: utf-8 -*-
import collections
import threading
import time
from typing import Any, Callable, Optional, Tuple

POLL_INTERVAL_SEC = 0.05

ERR_TIMEOUT = '이미지 수신 타임아웃 (%.1f초)'
ERR_STOPPED = '중단 요청'


class ImageFrameCache(object):

    MAX_FRAMES = 16

    def __init__(self, max_frames: int = MAX_FRAMES):
        self._lock = threading.Lock()
        self._seq = 0
        self._frames = collections.deque(maxlen=max_frames)
        self._at = 0.0

    def push(self, frame: Any) -> int:
        with self._lock:
            self._seq += 1
            self._at = time.monotonic()
            self._frames.append((self._seq, frame, self._at))
            return self._seq

    def baseline(self) -> int:
        with self._lock:
            return self._seq

    def peek(self) -> Tuple[Optional[Any], int, float]:
        with self._lock:
            if not self._frames:
                return None, self._seq, self._at
            seq, frame, at = self._frames[-1]
            return frame, seq, at

    def take_after(self, baseline: int) -> Optional[Any]:
        with self._lock:
            for seq, frame, _at in self._frames:
                if seq > baseline:
                    return frame
        return None

    def wait_after(self, baseline: int, timeout_sec: float,
                   should_stop: Optional[Callable[[], bool]] = None,
                   on_poll: Optional[Callable[[], None]] = None,
                   poll_interval: float = POLL_INTERVAL_SEC
                   ) -> Tuple[Optional[Any], Optional[str]]:
        start = time.monotonic()
        while True:
            frame = self.take_after(baseline)
            if frame is not None:
                return frame, None
            if should_stop is not None and should_stop():
                return None, ERR_STOPPED
            if time.monotonic() - start > timeout_sec:
                return None, ERR_TIMEOUT % timeout_sec
            if on_poll is not None:
                on_poll()
            else:
                time.sleep(poll_interval)
