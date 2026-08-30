"""조인트 각도 한계 실시간 감시 — 위반 시 로그 + 정지 콜백 1회(latch).

joints_deg 는 J1~J6 deg. 판정은 safety_area.check_joints 에 위임하며,
정지 콜백은 감시 콜백 스레드에서 불리므로 fire-and-forget 이어야 한다
(RobotStopService.stop — stop_sync 금지).
"""
from typing import Callable, Optional, Sequence

from . import safety_area as sa

REARM_HYSTERESIS_DEG = 1.0


class JointGuard:
    """연속 조인트 표본을 판정해 첫 위반에서만 정지를 부르고, 복귀하면 재무장한다."""

    def __init__(self, area: dict, stop_fn: Optional[Callable] = None,
                 log_callback: Optional[Callable[[str], None]] = None):
        self._area = area
        self._stop_fn = stop_fn
        self._log = log_callback or (lambda message: None)
        self._tripped = False

    def update(self, joints_deg: Sequence[float]) -> Optional[str]:
        """새 조인트 표본(deg)을 판정한다. 위반이면 사유를 돌려준다 (정상 None).

        위반 첫 표본에서만 로그·정지 콜백을 부르고 latch 한다 — 복귀 후
        REARM_HYSTERESIS_DEG 만큼 더 안쪽으로 들어와야 재무장한다.
        """
        if not sa.joint_limits_enabled(self._area):
            return None

        ok, reason = sa.check_joints(self._area, joints_deg)
        if ok:
            if self._tripped:
                rearmed, _ = sa.check_joints(
                    self._area, joints_deg, extra_margin_deg=REARM_HYSTERESIS_DEG)
                if rearmed:
                    self._tripped = False
                    self._log('[조인트한계] 범위 복귀 — 감시 재무장')
            return None

        if not self._tripped:
            self._tripped = True
            self._log(f'[조인트한계] 위반 — {reason}')
            if sa.joint_limits_config(self._area).get('auto_stop', True) and self._stop_fn:
                self._log('[조인트한계] 자동 정지 호출')
                try:
                    self._stop_fn()
                except Exception as e:
                    self._log(f'[조인트한계] 정지 호출 실패: {e}')
        return reason
