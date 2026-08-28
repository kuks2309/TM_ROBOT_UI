# -*- coding: utf-8 -*-
"""TMflow 카메라 프레임 캐시 — 어느 프레임이 «이번 요청의 것»인지 가린다.

ROS2 에 의존하지 않는다 — 로봇 없이 테스트된다.
(같은 규약을 쓰는 곳: services/pallet_recipe_generator.py)

## 왜 필요한가

예전에는 노드가 상태를 두 칸만 들고 있었다:

    waiting_for_techman_image (bool)
    current_techman_image     (msg)

그리고 콜백이 이랬다:

    if waiting_for_techman_image:      # 대기 중이 아니면
        current_techman_image = msg    #   ← 저장조차 안 했다
        waiting_for_techman_image = False

여기서 현장 증상 «찍어도 UI 에 안 뜬다»(2026-08-27 사용자 보고)가 나왔다:

  · 촬영 명령을 보낸 뒤 대기 루프에 **들어가기 직전**에 도착한 프레임은 버려졌다.
    그 뒤로는 아무것도 안 와서 타임아웃까지 기다리다 실패했다.
  · 반대로 이전 캡처의 늦은 프레임이 대기 시작 **직후**에 들어오면 그것을 이번
    사진으로 오인했다. QoS depth 가 10 이라 밀려 있을 여지가 컸다.
  · 이 두 칸을 소비자 3곳(UI 캡처 버튼 · 레시피 비전 잡 · 영상 처리)이 공유해,
    한쪽의 요청이 다른 쪽의 결과를 지우거나 남의 이미지를 가져갔다.

## 어떻게 바꿨나

  1. 대기 여부와 **무관하게** 항상 최신 프레임을 남긴다 (`push`).
  2. 프레임마다 일련번호를 매긴다.
  3. 소비자는 요청 시점의 번호(baseline)를 받아 두고, 그보다 **뒤에 도착한**
     프레임만 자기 것으로 가져간다 (`wait_after`).

소비자마다 baseline 을 따로 들고 있으므로 동시에 기다려도 서로 간섭하지 않는다.
"""
import collections
import threading
import time
from typing import Any, Callable, Optional, Tuple

POLL_INTERVAL_SEC = 0.05

ERR_TIMEOUT = '이미지 수신 타임아웃 (%.1f초)'
ERR_STOPPED = '중단 요청'


class ImageFrameCache(object):
    """최신 프레임 + 일련번호. 스레드 안전."""

    #: 보관할 최근 프레임 수. 소비자가 수거하기 전에 다음 프레임이 덮어써
    #: 남의 사진을 가져가는 일을 막는다. 이미지 원본을 들고 있으므로 과하게
    #: 키우지 않는다 (구독 QoS depth 가 10 이라 그와 같은 자릿수면 충분하다).
    MAX_FRAMES = 16

    def __init__(self, max_frames: int = MAX_FRAMES):
        self._lock = threading.Lock()
        self._seq = 0
        self._frames = collections.deque(maxlen=max_frames)   # [(seq, frame, at)]
        self._at = 0.0

    # ------------------------------------------------------------- 쓰기
    def push(self, frame: Any) -> int:
        """프레임 도착. 대기자가 없어도 **항상** 보관한다. 반환: 새 일련번호."""
        with self._lock:
            self._seq += 1
            self._at = time.monotonic()
            self._frames.append((self._seq, frame, self._at))
            return self._seq

    # ------------------------------------------------------------- 읽기
    def baseline(self) -> int:
        """지금까지 받은 마지막 번호. 이 값보다 큰 것만 «이번 요청의 것»이다."""
        with self._lock:
            return self._seq

    def peek(self) -> Tuple[Optional[Any], int, float]:
        """(프레임, 번호, 수신시각). 대기 없이 현재 값만 본다."""
        with self._lock:
            if not self._frames:
                return None, self._seq, self._at
            seq, frame, at = self._frames[-1]
            return frame, seq, at

    def take_after(self, baseline: int) -> Optional[Any]:
        """`baseline` 뒤에 **처음** 도착한 프레임. 없으면 None.

        최신 것이 아니라 «가장 이른 것» 을 준다 — 소비자가 원하는 것은 자기
        요청에 대한 응답이지, 그 뒤에 남이 찍은 사진이 아니다.
        버퍼에서 밀려났으면(너무 늦게 수거) 남아 있는 가장 이른 것을 준다.
        """
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
        """`baseline` 뒤 프레임을 기다린다.

        Args:
            baseline: `baseline()` 로 받아 둔 값.
            timeout_sec: 이 시간이 지나면 포기한다.
            should_stop: True 를 돌려주면 즉시 중단한다.
            on_poll: 매 폴링마다 부른다. 자체 실행기가 없는 호출부가
                여기서 `rclpy.spin_once()` 를 돌린다.

        Returns:
            (frame, error) — frame 이 None 이면 error 에 사유가 담긴다.
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
