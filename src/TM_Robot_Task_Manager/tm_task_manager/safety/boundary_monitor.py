"""실시간 경계 감시 — 이동 중 로봇이 구역을 침범하면 즉시 정지시킨다.

판정부(BoundaryJudge)는 순수 로직이라 로봇 없이 테스트할 수 있고, 감시 스레드
(BoundaryMonitor)는 샘플 함수·정지 함수를 주입받으므로 ROS2 에 의존하지 않는다.

## 왜 점이 아니라 선분으로 보는가

폴링은 이산 표본이다. 20Hz 로 보더라도 TCP 가 500mm/s 로 움직이면 표본 간격이 25mm 라,
점만 검사하면 그 사이에 있는 얇은 구역을 통째로 건너뛴다. 직전 표본과 현재 표본을
**선분으로 이어** 판정하면 표본 간격과 무관하게 침범을 놓치지 않는다.

## 정지 지연은 별개 문제다

침범을 놓치지 않는 것과 침범 전에 멈추는 것은 다르다. 정지 명령이 먹히기까지 로봇은
계속 가므로, `margin_mm` 이 제동거리보다 작으면 "정지했는데 이미 들어가 있는" 상태가 된다.
제동거리는 실기에서 측정해 margin 하한을 역산해야 한다.
"""
import threading
import time
from typing import Callable, List, Optional, Sequence, Tuple

from . import safety_area as sa

DEFAULT_POLL_SEC = 0.05

STATE_IDLE = 'idle'
STATE_WATCHING = 'watching'
STATE_STOPPED = 'stopped'


class BoundaryJudge:
    """표본을 순서대로 받아 침범 시점을 찾아낸다 — 순수 로직."""

    def __init__(self, area: dict):
        self._area = area
        self._previous: Optional[List[float]] = None

    @property
    def previous(self) -> Optional[List[float]]:
        return self._previous

    def reset(self) -> None:
        self._previous = None

    def update(self, point_mm: Sequence[float]) -> Optional[str]:
        """표본 1개를 넣는다. 침범이면 사유 문자열을, 아니면 None 을 돌려준다.

        첫 표본은 이을 상대가 없어 점으로 보고, 이후로는 직전 표본과의 선분으로 본다.
        """
        if not sa.is_enabled(self._area):
            self._previous = list(point_mm)
            return None

        current = [float(point_mm[i]) for i in range(3)]

        if self._previous is None:
            ok, reason = sa.check_point(self._area, current)
        else:
            ok, reason = sa.check_segment(self._area, self._previous, current)

        self._previous = current
        return None if ok else reason


class BoundaryMonitor:
    """이동 중 감시 스레드. 침범을 찾으면 stop_fn 을 **한 번만** 부르고 멈춘다.

    sample_fn 은 현재 TCP 자세([x, y, z, …] mm) 또는 None 을 돌려준다.
    stop_fn 은 (ok, message) 를 돌려주는 로봇 정지 함수다.
    """

    def __init__(self, area: dict,
                 sample_fn: Callable[[], Optional[Sequence[float]]],
                 stop_fn: Callable[[], Tuple[bool, str]],
                 poll_sec: float = DEFAULT_POLL_SEC,
                 on_violation: Optional[Callable[[str], None]] = None,
                 log_callback: Optional[Callable[[str], None]] = None):
        self._area = area
        self._sample_fn = sample_fn
        self._stop_fn = stop_fn
        self._poll_sec = poll_sec
        self._on_violation = on_violation
        self._log_callback = log_callback

        self._judge = BoundaryJudge(area)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._state = STATE_IDLE
        self._message = ''

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def message(self) -> str:
        with self._lock:
            return self._message

    @property
    def is_watching(self) -> bool:
        return self.state == STATE_WATCHING

    def set_area(self, area: dict) -> None:
        self._area = area
        self._judge = BoundaryJudge(area)

    def _log(self, message: str) -> None:
        if self._log_callback:
            self._log_callback(message)

    def start(self) -> bool:
        """감시를 시작한다. 구역이 꺼져 있거나 이미 돌고 있으면 아무것도 하지 않는다."""
        if not sa.is_enabled(self._area):
            return False
        with self._lock:
            if self._state == STATE_WATCHING:
                return False
            self._state = STATE_WATCHING
            self._message = ''
        self._judge.reset()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name='safety-boundary', daemon=True)
        self._thread.start()
        return True

    def stop(self, timeout: float = 1.0) -> None:
        """감시를 끝낸다. 로봇을 정지시키지는 않는다 — 이동이 정상 종료됐을 때 부른다."""
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
        self._thread = None
        with self._lock:
            if self._state == STATE_WATCHING:
                self._state = STATE_IDLE

    def reset(self) -> None:
        """정지 상태를 푼다. 탈출 이동을 허용하기 전에 부른다."""
        with self._lock:
            self._state = STATE_IDLE
            self._message = ''
        self._judge.reset()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            sample = None
            try:
                sample = self._sample_fn()
            except Exception as exc:
                self._log(f'[안전구역] 위치 표본 획득 실패: {exc}')

            if sample is not None and len(sample) >= 3:
                reason = self._judge.update(sample)
                if reason:
                    self._trigger_stop(reason)
                    return

            self._stop_event.wait(self._poll_sec)

    def _trigger_stop(self, reason: str) -> None:
        with self._lock:
            if self._state != STATE_WATCHING:
                return
            self._state = STATE_STOPPED
            self._message = f'[안전구역] 침범으로 자동 정지했습니다 — {reason}'
            message = self._message

        self._log(message)

        try:
            ok, stop_msg = self._stop_fn()
        except Exception as exc:
            ok, stop_msg = False, str(exc)

        if not ok:
            failure = f'[안전구역] 자동 정지 명령이 실패했습니다 — {stop_msg}'
            with self._lock:
                self._message += f' / {failure}'
            self._log(failure)

        if self._on_violation:
            self._on_violation(message)
