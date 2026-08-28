import math
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence

from . import safety_area as sa

MOTION_LINE = 'line'
MOTION_LINE_RELATIVE = 'line_relative'
MOTION_PTP_TCP = 'ptp_tcp'
MOTION_PTP_JOINT = 'ptp_joint'
MOTION_VISION_JOB = 'vision_job'

EXACT_KINDS = (MOTION_LINE, MOTION_LINE_RELATIVE)
PTP_KINDS = (MOTION_PTP_TCP, MOTION_PTP_JOINT)

MAX_RECORDS = 200


@dataclass
class GuardDecision:

    allowed: bool
    kind: str
    reason: str = ''
    checked: bool = False
    note: str = ''
    label: str = ''
    start_mm: Optional[List[float]] = None
    target_mm: Optional[List[float]] = None

    def summary(self) -> str:
        verdict = '허용' if self.allowed else '거부'
        mark = '검사함' if self.checked else '미검사'
        head = f'[안전구역] {verdict}/{mark} {self.label or self.kind}'
        tail = self.reason or self.note
        return f'{head} — {tail}' if tail else head


def rotation_matrix_deg(rx_deg: float, ry_deg: float, rz_deg: float) -> List[List[float]]:
    rx, ry, rz = math.radians(rx_deg), math.radians(ry_deg), math.radians(rz_deg)
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    return [
        [cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx],
        [sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx],
        [-sy, cy * sx, cy * cx],
    ]


def tool_offset_to_base(tcp_pose: Sequence[float],
                        dx: float, dy: float, dz: float) -> List[float]:
    R = rotation_matrix_deg(tcp_pose[3], tcp_pose[4], tcp_pose[5])
    offset = (float(dx), float(dy), float(dz))
    return [
        float(tcp_pose[i]) + sum(R[i][k] * offset[k] for k in range(3))
        for i in range(3)
    ]


class MotionGuard:

    def __init__(self, area: Optional[dict] = None,
                 log_callback: Optional[Callable[[str], None]] = None):
        self._area = area if area is not None else sa.load_area()
        self._log_callback = log_callback
        self._records: List[GuardDecision] = []

    @property
    def area(self) -> dict:
        return self._area

    @property
    def enabled(self) -> bool:
        return sa.is_enabled(self._area)

    def reload(self, path: Optional[str] = None) -> dict:
        self._area = sa.load_area(path)
        return self._area

    def set_area(self, area: dict) -> None:
        self._area = area

    def records(self) -> List[GuardDecision]:
        return list(self._records)

    def unchecked_records(self) -> List[GuardDecision]:
        return [r for r in self._records if r.allowed and not r.checked]

    def clear_records(self) -> None:
        self._records.clear()

    def _log(self, message: str) -> None:
        if self._log_callback:
            self._log_callback(message)

    def _record(self, decision: GuardDecision) -> GuardDecision:
        self._records.append(decision)
        if len(self._records) > MAX_RECORDS:
            del self._records[:-MAX_RECORDS]
        if not decision.allowed or not decision.checked:
            self._log(decision.summary())
        return decision

    def check(self, kind: str, tcp_pose: Optional[Sequence[float]] = None,
              target_mm: Optional[Sequence[float]] = None,
              offset_mm: Optional[Sequence[float]] = None,
              label: str = '') -> GuardDecision:
        if not self.enabled:
            return self._record(GuardDecision(
                allowed=True, kind=kind, label=label, checked=False,
                note='안전 구역 비활성 — 제약 없음'))

        if kind == MOTION_VISION_JOB:
            return self._record(GuardDecision(
                allowed=True, kind=kind, label=label, checked=False,
                note='TMflow 잡 내부에 목표가 있어 좌표를 알 수 없습니다 — 미검사로 기록합니다'))

        if kind in PTP_KINDS:
            return self._record(GuardDecision(
                allowed=False, kind=kind, label=label, checked=False,
                reason='PTP 는 실경로가 직선이 아니어서 경로를 보증할 수 없습니다 — '
                       '안전 구역이 켜져 있는 동안 거부합니다. 직선(Line) 이동을 쓰십시오.'))

        if kind not in EXACT_KINDS:
            return self._record(GuardDecision(
                allowed=False, kind=kind, label=label, checked=False,
                reason=f'해석할 수 없는 모션 종류({kind}) 입니다 — 안전 구역이 켜져 있어 거부합니다.'))

        if not tcp_pose or len(tcp_pose) < 6:
            return self._record(GuardDecision(
                allowed=False, kind=kind, label=label, checked=False,
                reason='현재 로봇 위치를 알 수 없습니다 — 경로 검증 불가로 거부합니다.'))

        start_mm = [float(tcp_pose[0]), float(tcp_pose[1]), float(tcp_pose[2])]

        if kind == MOTION_LINE_RELATIVE:
            if offset_mm is None or len(offset_mm) < 3:
                return self._record(GuardDecision(
                    allowed=False, kind=kind, label=label, checked=False,
                    start_mm=start_mm,
                    reason='상대 이동 오프셋이 없습니다 — 검증 불가로 거부합니다.'))
            end_mm = tool_offset_to_base(tcp_pose, offset_mm[0], offset_mm[1], offset_mm[2])
        else:
            if target_mm is None or len(target_mm) < 3:
                return self._record(GuardDecision(
                    allowed=False, kind=kind, label=label, checked=False,
                    start_mm=start_mm,
                    reason='목표 좌표가 없습니다 — 검증 불가로 거부합니다.'))
            end_mm = [float(target_mm[0]), float(target_mm[1]), float(target_mm[2])]

        start_bad = (not sa.point_in_area(self._area, start_mm)
                     or bool(sa.keep_out_hits(self._area, start_mm)))
        if start_bad:
            ok, reason = sa.check_point(self._area, end_mm)
            note = ('현재 위치가 이미 위반 상태입니다 — 갇히지 않도록 목표점만 검사했습니다.')
            return self._record(GuardDecision(
                allowed=ok, kind=kind, label=label, checked=True, note=note,
                reason='' if ok else reason, start_mm=start_mm, target_mm=end_mm))

        ok, reason = sa.check_segment(self._area, start_mm, end_mm)
        return self._record(GuardDecision(
            allowed=ok, kind=kind, label=label, checked=True,
            reason='' if ok else reason, start_mm=start_mm, target_mm=end_mm))
