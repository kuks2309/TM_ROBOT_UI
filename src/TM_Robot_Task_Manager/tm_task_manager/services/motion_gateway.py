"""모션 단일 관문 — 로봇을 움직이는 모든 명령이 여기를 지난다.

## 왜 관문이 필요한가

이 워크스페이스는 모션 명령이 다섯 갈래로 나간다: `main_window._call_set_positions`,
`job_executor` 의 자체 SetPositions 클라이언트, `Move_Line("TPP", …)`,
`TmRobotScriptMotion` 의 `Line`/`PTP`/`Move_Line`, `handeye_test_manager` 의 `Line`.
가드를 한 곳에만 달면 나머지 네 곳이 그대로 샌다. 그래서 판정·감시·전송을 이 한 곳에 모으고
호출부는 전부 여기를 통과시킨다.

전송 자체는 호출자가 넘긴 sender 가 한다 — 관문은 ROS2 를 모른다.
"""
from contextlib import contextmanager
from typing import Callable, Optional, Sequence, Tuple

from ..safety import motion_guard as mg
from ..safety.boundary_monitor import STATE_STOPPED

Sender = Callable[[], Tuple[bool, str]]


class MotionGateway:
    """사전 검사 → 감시 시작 → 전송 → 감시 종료 를 한 묶음으로 수행한다."""

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
        """직전 자동 정지 상태를 푼다.

        정지 뒤에는 로봇이 위반 지점에 서 있다. 가드가 '시작점이 이미 위반이면 목표점만
        검사' 로 탈출을 허용하므로, 감시 상태만 풀어 주면 깨끗한 목표로는 빠져나갈 수 있다.
        """
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
        """전송 없이 판정만 한다. 화면에서 미리 경고를 띄울 때 쓴다."""
        return self._guard.check(
            kind, tcp_pose=self._tcp_pose(), target_mm=target_mm,
            offset_mm=offset_mm, label=label)

    def send(self, kind: str, sender: Sender,
             target_mm: Optional[Sequence[float]] = None,
             offset_mm: Optional[Sequence[float]] = None,
             label: str = '', watch: bool = True) -> Tuple[bool, str]:
        """판정을 통과하면 sender 로 전송한다. 거부면 전송하지 않는다.

        watch=False 면 실시간 감시를 걸지 않는다 — 전송이 즉시 반환하고 이동이 그 뒤로도
        이어지는 경우, 호출부가 감시 수명을 직접 관리해야 할 때 쓴다.
        """
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
        """비전 잡 — 좌표가 명령에 없어 사전 검사를 못 한다. 미검사로 기록하고 통과시킨다."""
        return self.send(mg.MOTION_VISION_JOB, sender, label=label, watch=watch)
