"""모션 명령 사전 검사 — 로봇이 움직이기 전에 목표·경로를 판정해 경고하고 차단한다.

ROS2 에 의존하지 않는다. 현재 TCP 자세는 호출자가 넘긴다.

## 판정 정책

| 종류 | 판정 | 근거 |
| --- | --- | --- |
| `LINE` / `LINE_RELATIVE` | 현재 TCP → 목표 **선분 전체** | 실경로가 직선으로 보장된다 |
| `PTP_TCP` / `PTP_JOINT` | 구역 활성 시 **거부** | 실경로가 직선이 아니라 판정이 근사다 (사용자 결정) |
| `VISION_JOB` | **통과하되 미검사로 기록** | 목표가 TMflow 잡 내부라 좌표가 명령에 없다 (사용자 결정) |
| 해석 불가 | 거부 | 조용히 새는 경로를 만들지 않는다 |

`VISION_JOB` 은 좌표를 알 수 없어 검사할 수 없다. 막지 않는 대신 `checked=False` 로
남겨, 어떤 이동이 좌표 검사 없이 나갔는지 나중에 감사할 수 있게 한다.
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
    """가드 판정 1건. 기록으로 남길 수 있도록 판정 근거를 모두 담는다."""

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
    """RPY(도) → 회전행렬 R = Rz·Ry·Rx.

    RobotMotionService._quaternion_to_euler_deg 가 만드는 각과 같은 규약이라,
    그 각을 그대로 넣으면 툴 좌표계 → 베이스 좌표계 변환이 된다.
    """
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
    """툴 좌표계 상대 오프셋(mm) → 베이스 좌표계 절대 목표(mm).

    Move_Line("TPP", …) 은 툴 기준 상대 이동이라, 현재 자세의 회전을 곱해야
    베이스 좌표계에서의 목표점이 나온다.
    """
    R = rotation_matrix_deg(tcp_pose[3], tcp_pose[4], tcp_pose[5])
    offset = (float(dx), float(dy), float(dz))
    return [
        float(tcp_pose[i]) + sum(R[i][k] * offset[k] for k in range(3))
        for i in range(3)
    ]


class MotionGuard:
    """안전 구역 정의를 들고 모션 명령을 판정한다. 판정 기록을 누적한다."""

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
        """설정 파일을 다시 읽는다. 웹·GUI 에서 구역을 바꾼 뒤 호출한다."""
        self._area = sa.load_area(path)
        return self._area

    def set_area(self, area: dict) -> None:
        self._area = area

    def records(self) -> List[GuardDecision]:
        return list(self._records)

    def unchecked_records(self) -> List[GuardDecision]:
        """좌표 검사 없이 통과한 이동만. 감사·리뷰용."""
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
        """모션 명령 1건을 판정한다.

        kind 가 LINE 이면 target_mm 을, LINE_RELATIVE 면 offset_mm 을 준다.
        tcp_pose 는 [x, y, z, rx, ry, rz] (mm, 도) 로 현재 자세다.
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
