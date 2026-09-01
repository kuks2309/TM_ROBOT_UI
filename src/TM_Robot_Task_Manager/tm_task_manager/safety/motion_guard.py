"""이동 명령 사전 안전 게이트 — 모션 종류별로 구역 판정 후 허용/거부를 기록한다.

좌표계 전제: tcp_pose·target_mm 은 로봇 베이스 좌표계 mm 로 가정하며 코드가
이를 강제하지 않는다 — ChangeBase 로 다른 좌표계(vision base 등)에 있는 동안
Line 목표를 넘기면 베이스 구역과 잘못 대조된다. 호출측이 좌표계를 보장할 것.
"""
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
    """한 번의 이동 검사 결과 (허용 여부·검사 여부·사유·시작/목표점 mm)."""

    allowed: bool
    kind: str
    reason: str = ''
    checked: bool = False
    note: str = ''
    label: str = ''
    start_mm: Optional[List[float]] = None
    target_mm: Optional[List[float]] = None

    def summary(self) -> str:
        """허용/거부·검사 여부·사유를 한 줄 로그 문장으로 만든다."""
        verdict = '허용' if self.allowed else '거부'
        mark = '검사함' if self.checked else '미검사'
        head = f'[안전구역] {verdict}/{mark} {self.label or self.kind}'
        tail = self.reason or self.note
        return f'{head} — {tail}' if tail else head


def rotation_matrix_deg(rx_deg: float, ry_deg: float, rz_deg: float) -> List[List[float]]:
    """오일러 각(deg)에서 Rz·Ry·Rx 순 합성 3x3 회전행렬을 만든다 (순수 파이썬)."""
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
    """공구 좌표계 오프셋(mm)을 현재 TCP 자세로 회전시켜 베이스 목표점(mm)으로 환산한다."""
    R = rotation_matrix_deg(tcp_pose[3], tcp_pose[4], tcp_pose[5])
    offset = (float(dx), float(dy), float(dz))
    return [
        float(tcp_pose[i]) + sum(R[i][k] * offset[k] for k in range(3))
        for i in range(3)
    ]


class MotionGuard:
    """모션 종류별 사전 판정기.

    구역 활성 시 정책: Line 계열만 시작-목표 선분을 정확 검사, PTP 는 실경로
    비보증으로 무조건 거부, vision_job 은 목표 좌표 불명으로 '미검사 허용'.
    기록(_records)은 락 없이 다루므로 단일 스레드(GUI/executor 계열) 호출 전제.
    """

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
        """설정 파일에서 구역을 다시 읽어 적용하고 돌려준다."""
        self._area = sa.load_area(path)
        return self._area

    def set_area(self, area: dict) -> None:
        self._area = area

    def records(self) -> List[GuardDecision]:
        """판정 기록 사본 (최대 MAX_RECORDS 건)."""
        return list(self._records)

    def unchecked_records(self) -> List[GuardDecision]:
        """'허용됐지만 미검사'인 기록만 — 무검사 통과분 감사용."""
        return [r for r in self._records if r.allowed and not r.checked]

    def clear_records(self) -> None:
        self._records.clear()

    def _log(self, message: str) -> None:
        if self._log_callback:
            self._log_callback(message)

    def _record(self, decision: GuardDecision) -> GuardDecision:
        """기록 append 후 상한 트림 — 거부/미검사 건만 로그로 띄운다."""
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
        """이동 한 건을 판정해 기록한다.

        Args:
            kind: MOTION_* 상수 중 하나.
            tcp_pose: 현재 TCP [x,y,z,rx,ry,rz] (베이스 좌표계 mm/deg).
            target_mm: 절대 목표점 (line/ptp 용, 베이스 mm).
            offset_mm: 공구 좌표계 상대 오프셋 (line_relative 용, mm).

        시작점이 이미 위반 상태면 갇힘 방지를 위해 목표점만 검사한다
        (구역 밖에서 안으로 복귀하는 이동을 허용하기 위해).
        """
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
