from contextlib import contextmanager
from typing import Callable, Optional, Sequence, Tuple

from ..safety import motion_guard as mg
from ..safety.boundary_monitor import STATE_STOPPED

Sender = Callable[[], Tuple[bool, str]]


class MotionGateway:

    def __init__(self, guard: mg.MotionGuard,
                 tcp_pose_fn: Optional[Callable[[], Optional[Sequence[float]]]] = None,
                 monitor=None,
                 log_callback: Optional[Callable[[str], None]] = None):
        self._guard = guard
        self._tcp_pose_fn = tcp_pose_fn
        self._monitor = monitor
        self._log_callback = log_callback

    @property
    def guard(self) -> mg.MotionGuard:
        return self._guard

    @property
    def monitor(self):
        return self._monitor

    def set_monitor(self, monitor) -> None:
        self._monitor = monitor

    def _log(self, message: str) -> None:
        if self._log_callback:
            self._log_callback(message)

    def _tcp_pose(self) -> Optional[Sequence[float]]:
        if self._tcp_pose_fn is None:
            return None
        try:
            return self._tcp_pose_fn()
        except Exception:
            return None

    def _clear_stopped_state(self) -> None:
        if self._monitor is not None and self._monitor.state == STATE_STOPPED:
            self._log('[안전구역] 직전 자동 정지 상태를 해제합니다 — 목표점 검사로 탈출을 허용합니다.')
            self._monitor.reset()

    @contextmanager
    def _watching(self):
        started = False
        if self._monitor is not None:
            started = self._monitor.start()
        try:
            yield
        finally:
            if started:
                self._monitor.stop()

    def check(self, kind: str, target_mm: Optional[Sequence[float]] = None,
              offset_mm: Optional[Sequence[float]] = None,
              label: str = '') -> mg.GuardDecision:
        return self._guard.check(
            kind, tcp_pose=self._tcp_pose(), target_mm=target_mm,
            offset_mm=offset_mm, label=label)

    def send(self, kind: str, sender: Sender,
             target_mm: Optional[Sequence[float]] = None,
             offset_mm: Optional[Sequence[float]] = None,
             label: str = '', watch: bool = True) -> Tuple[bool, str]:
        self._clear_stopped_state()

        decision = self._guard.check(
            kind, tcp_pose=self._tcp_pose(), target_mm=target_mm,
            offset_mm=offset_mm, label=label)

        if not decision.allowed:
            return False, decision.reason

        if not watch:
            return sender()

        with self._watching():
            ok, message = sender()

        if self._monitor is not None and self._monitor.state == STATE_STOPPED:
            return False, self._monitor.message

        return ok, message

    def send_line(self, sender: Sender, target_mm: Sequence[float],
                  label: str = 'Line', watch: bool = True) -> Tuple[bool, str]:
        return self.send(mg.MOTION_LINE, sender, target_mm=target_mm,
                         label=label, watch=watch)

    def send_line_relative(self, sender: Sender, offset_mm: Sequence[float],
                           label: str = 'Move_Line', watch: bool = True) -> Tuple[bool, str]:
        return self.send(mg.MOTION_LINE_RELATIVE, sender, offset_mm=offset_mm,
                         label=label, watch=watch)

    def send_ptp_tcp(self, sender: Sender, target_mm: Optional[Sequence[float]] = None,
                     label: str = 'PTP', watch: bool = True) -> Tuple[bool, str]:
        return self.send(mg.MOTION_PTP_TCP, sender, target_mm=target_mm,
                         label=label, watch=watch)

    def send_ptp_joint(self, sender: Sender, label: str = 'PTP_J',
                       watch: bool = True) -> Tuple[bool, str]:
        return self.send(mg.MOTION_PTP_JOINT, sender, label=label, watch=watch)

    def send_vision_job(self, sender: Sender, label: str = 'Vision_DoJob',
                        watch: bool = True) -> Tuple[bool, str]:
        return self.send(mg.MOTION_VISION_JOB, sender, label=label, watch=watch)
