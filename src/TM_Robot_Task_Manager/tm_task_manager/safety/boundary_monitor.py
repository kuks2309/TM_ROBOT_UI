"""이동 중 실시간 안전구역 감시 — 표본화 스레드가 위반 시 정지 콜백을 부른다.

좌표는 로봇 베이스 좌표계 mm. 판정 로직은 safety_area 에 위임한다.
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
    """연속 표본을 이어 붙여 점/선분 단위로 구역 위반을 판정한다."""

    def __init__(self, area: dict):
        self._area = area
        self._previous: Optional[List[float]] = None

    @property
    def previous(self) -> Optional[List[float]]:
        return self._previous

    def reset(self) -> None:
        """직전 표본을 지운다 — 다음 update 는 점 검사부터 다시 시작."""
        self._previous = None

    def update(self, point_mm: Sequence[float]) -> Optional[str]:
        """새 표본(mm)을 반영하고 위반 사유를 돌려준다 (정상이면 None).

        첫 표본은 점 검사, 이후는 직전 표본과 잇는 선분 검사 — 폴링 주기
        사이에 지나간 경로까지 커버하기 위해서다.
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
    """데몬 스레드로 TCP 위치를 표본화해 구역 침범 시 로봇을 자동 정지시킨다.

    sample_fn(현재 TCP mm)·stop_fn(정지 명령)은 주입 콜백 — 실체는 루트 노드
    소관이다. stop_fn 은 감시 스레드에서 불리므로 노드 spin 계열
    (spin_until_future_complete)을 물리면 이중 spin 이 된다 — call_async 만
    쓰는 비동기 정지 계열로 한정할 것. 상태는 idle/watching/stopped 3상.
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
        # _lock 은 _state/_message 만 보호 — GUI 스레드와 감시 스레드 양쪽에서 읽고 쓴다
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
        """감시 구역을 교체한다.

        락 없는 참조 스왑이라 감시 중 교체 시 진행 중인 판정 1회는 이전
        구역으로 끝날 수 있다 — stop 후 교체가 안전하다.
        """
        self._area = area
        self._judge = BoundaryJudge(area)

    def _log(self, message: str) -> None:
        if self._log_callback:
            self._log_callback(message)

    def start(self) -> bool:
        """감시 스레드를 기동한다 (구역 비활성/이미 감시 중이면 False)."""
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
        """감시 스레드를 종료 신호+join 으로 멈춘다 (STOPPED 상태는 유지).

        join 이 timeout(s) 안에 안 끝나도 반환한다 — stop_event 가 서 있어
        잔존 스레드는 다음 wait 에서 스스로 끝난다.
        """
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
        self._thread = None
        with self._lock:
            if self._state == STATE_WATCHING:
                self._state = STATE_IDLE

    def reset(self) -> None:
        """정지 이력(STOPPED 상태·메시지)을 지우고 idle 로 되돌린다."""
        with self._lock:
            self._state = STATE_IDLE
            self._message = ''
        self._judge.reset()

    def _run(self) -> None:
        """감시 루프: poll_sec 주기로 표본화→판정, 위반 시 정지 후 종료."""
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
        """(감시 스레드) STOPPED 전이 후 stop_fn 호출·위반 콜백 발화."""
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
