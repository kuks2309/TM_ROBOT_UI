import threading
import time
from typing import Callable, List, Optional, Sequence, Tuple

from . import safety_area as sa

DEFAULT_POLL_SEC = 0.05

STATE_IDLE = 'idle'
STATE_WATCHING = 'watching'
STATE_STOPPED = 'stopped'


class BoundaryJudge:

    def __init__(self, area: dict):
        self._area = area
        self._previous: Optional[List[float]] = None

    @property
    def previous(self) -> Optional[List[float]]:
        return self._previous

    def reset(self) -> None:
        self._previous = None

    def update(self, point_mm: Sequence[float]) -> Optional[str]:
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
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
        self._thread = None
        with self._lock:
            if self._state == STATE_WATCHING:
                self._state = STATE_IDLE

    def reset(self) -> None:
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
