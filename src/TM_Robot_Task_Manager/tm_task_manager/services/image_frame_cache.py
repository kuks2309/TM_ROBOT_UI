# -*- coding: utf-8 -*-
"""시퀀스 번호 링버퍼 이미지 캐시 — '기준 시점 이후 도착' 프레임만 취득한다."""
import collections
import threading
import time
from typing import Any, Callable, Optional, Tuple

POLL_INTERVAL_SEC = 0.05

ERR_TIMEOUT = '이미지 수신 타임아웃 (%.1f초)'
ERR_STOPPED = '중단 요청'


class ImageFrameCache(object):
    """수신 프레임에 단조 증가 시퀀스를 붙여 보관하는 링버퍼.

    baseline() 으로 현재 시퀀스를 찍고 take_after/wait_after 로 그 이후 프레임만
    취득한다 — 캡처 명령 이전에 남아 있던 낡은 프레임을 결과로 오인하지 않기
    위한 구조. push(구독 콜백 스레드)와 소비 스레드가 달라 락으로 보호한다.
    """

    MAX_FRAMES = 16

    def __init__(self, max_frames: int = MAX_FRAMES):
        self._lock = threading.Lock()
        self._seq = 0
        self._frames = collections.deque(maxlen=max_frames)
        self._at = 0.0

    def push(self, frame: Any) -> int:
        """프레임을 추가하고 부여한 시퀀스 번호를 돌려준다 (구독 콜백에서 호출)."""
        with self._lock:
            self._seq += 1
            self._at = time.monotonic()
            self._frames.append((self._seq, frame, self._at))
            return self._seq

    def baseline(self) -> int:
        """현재 시퀀스 — 이후 wait_after/take_after 의 기준점으로 쓴다."""
        with self._lock:
            return self._seq

    def peek(self) -> Tuple[Optional[Any], int, float]:
        """최신 프레임 (frame, seq, 수신 시각 monotonic s) — 없으면 (None, seq, at)."""
        with self._lock:
            if not self._frames:
                return None, self._seq, self._at
            seq, frame, at = self._frames[-1]
            return frame, seq, at

    def take_after(self, baseline: int) -> Optional[Any]:
        """baseline 초과 시퀀스의 첫 프레임 (없으면 None, 대기 없음)."""
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
        """baseline 이후 첫 프레임을 폴링 대기한다.

        on_poll 을 주면 sleep 대신 매 회 그것만 부른다 — push 를 진행시키는
        블로킹 호출(예: spin_once(timeout))이라는 전제이며, 논블로킹 콜러블을
        주면 busy-spin 이 된다.

        Returns:
            (frame, None) 또는 (None, 오류 문구 — ERR_TIMEOUT/ERR_STOPPED).
        """
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
