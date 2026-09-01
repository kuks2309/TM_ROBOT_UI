"""TMflow 스크립트(SendScript 채널) 모션 파사드.

gv_manager(GlobalVariableScript — 루트 소유 send_script 클라이언트)를 차용해
ChangeBase/Line/PTP/Move_Line 스크립트를 조립·전송한다. 좌표 인자는 스크립트가
실행되는 '현재 base' 기준 mm/deg — ChangeBase 후에는 RobotBase 가 아닐 수
있는데, gateway(MotionGuard) 검사는 베이스 좌표 전제라 이때 판정이 어긋난다.
"""
from typing import Tuple, Callable, Optional, Sequence

# send_raw_script 가 안전 구역 활성 시 거부하는 TMflow 모션 명령 접두어들
MOTION_KEYWORDS = (
    'Line(', 'PTP(', 'Move_Line(', 'Move_PTP(', 'Vision_DoJob_PTP(', 'Circle(',
)


class TmRobotScriptMotion:
    """스크립트 채널 이동 명령 조립기 — gateway 가 있으면 종류별 사전 검사를 통과해야 전송."""

    def __init__(self, gv_manager, log_callback: Callable[[str], None] = None,
                 gateway=None):
        self.gv_manager = gv_manager
        self._log_callback = log_callback
        self._gateway = gateway

    def set_gateway(self, gateway) -> None:
        self._gateway = gateway

    def _log(self, message: str):
        if self._log_callback:
            self._log_callback(message)

    def _guard(self, kind: str, label: str,
               target_mm: Optional[Sequence[float]] = None,
               offset_mm: Optional[Sequence[float]] = None) -> Tuple[bool, str]:
        """gateway.check 래퍼 — gateway 미주입이면 검사 없이 통과한다."""
        if self._gateway is None:
            return True, ''
        decision = self._gateway.check(
            kind, target_mm=target_mm, offset_mm=offset_mm, label=label)
        if decision.allowed:
            return True, ''
        self._log(f'[안전구역] {label} 거부 — {decision.reason}')
        return False, decision.reason

    def change_base(self, base_name: str) -> Tuple[bool, str]:
        """ChangeBase 스크립트로 TMflow 좌표계를 전환한다 — 이후 이동 좌표 해석이 바뀐다."""
        if not self.gv_manager:
            return False, "GlobalVariableScript가 없습니다"

        script = f'ChangeBase("{base_name}")'
        self._log(f"ChangeBase 실행: {base_name}")

        success, msg = self.gv_manager.send_script(script)
        if success:
            return True, f"좌표계 변경 완료: {base_name}"
        else:
            return False, f"ChangeBase 실패: {msg}"

    def line_cpp(
        self,
        x: float,
        y: float,
        z: float,
        rx: float,
        ry: float,
        rz: float,
        velocity_mm: float = 100.0,
        acc_time_ms: int = 200,
        blend_percent: int = 0,
        fine_goal: bool = True
    ) -> Tuple[bool, str]:
        """Line("CPP") 직선 이동 — 현재 base 기준 mm/deg, 속도 mm/s, 가속 ms."""
        if not self.gv_manager:
            return False, "GlobalVariableScript가 없습니다"

        ok, reason = self._guard('line', 'Line CPP', target_mm=[x, y, z])
        if not ok:
            return False, reason

        vel = int(velocity_mm)
        fine = "true" if fine_goal else "false"

        script = f'Line("CPP", {x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc_time_ms}, {blend_percent}, {fine})'
        self._log(f"Line CPP: X={x}, Y={y}, Z={z}, Rx={rx}, Ry={ry}, Rz={rz}, V={vel}mm/s")

        success, msg = self.gv_manager.send_script(script)
        if success:
            return True, f"Line CPP 완료"
        else:
            return False, f"Line CPP 실패: {msg}"

    def ptp_cpp(
        self,
        x: float,
        y: float,
        z: float,
        rx: float,
        ry: float,
        rz: float,
        velocity_percent: float = 10.0,
        acc_time_ms: int = 200,
        blend_percent: int = 0,
        fine_goal: bool = True
    ) -> Tuple[bool, str]:
        """PTP("CPP") 이동 — 속도는 % (안전 구역 활성 시 guard 가 PTP 를 거부한다)."""
        if not self.gv_manager:
            return False, "GlobalVariableScript가 없습니다"

        ok, reason = self._guard('ptp_tcp', 'PTP CPP', target_mm=[x, y, z])
        if not ok:
            return False, reason

        vel = int(velocity_percent)
        fine = "true" if fine_goal else "false"

        script = f'PTP("CPP", {x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc_time_ms}, {blend_percent}, {fine})'
        self._log(f"PTP CPP: X={x}, Y={y}, Z={z}, Rx={rx}, Ry={ry}, Rz={rz}, V={vel}%")

        success, msg = self.gv_manager.send_script(script)
        if success:
            return True, f"PTP CPP 완료"
        else:
            return False, f"PTP CPP 실패: {msg}"

    def line_relative(
        self,
        dx: float = 0,
        dy: float = 0,
        dz: float = 0,
        drx: float = 0,
        dry: float = 0,
        drz: float = 0,
        velocity_mm: float = 100.0,
        acc_time_ms: int = 200
    ) -> Tuple[bool, str]:
        """Move_Line("TPP") 공구 좌표계 상대 직선 이동 — 오프셋 mm/deg, 속도 mm/s."""
        if not self.gv_manager:
            return False, "GlobalVariableScript가 없습니다"

        ok, reason = self._guard('line_relative', 'Move_Line TPP', offset_mm=[dx, dy, dz])
        if not ok:
            return False, reason

        vel = int(velocity_mm)
        script = f'Move_Line("TPP", {dx}, {dy}, {dz}, {drx}, {dry}, {drz}, {vel}, {acc_time_ms}, 0, true)'
        self._log(f"Line 상대이동: dX={dx}, dY={dy}, dZ={dz}, V={vel}mm/s")

        success, msg = self.gv_manager.send_script(script)
        if success:
            return True, f"상대 이동 완료"
        else:
            return False, f"상대 이동 실패: {msg}"

    def send_raw_script(self, script: str) -> Tuple[bool, str]:
        """임의 스크립트 전송 — 구역 활성 시 모션 키워드 포함 스크립트는 거부.

        gateway 미주입이면 키워드 필터 없이 그대로 전송된다.
        """
        if not self.gv_manager:
            return False, "GlobalVariableScript가 없습니다"

        if self._gateway is not None and self._gateway.guard.enabled:
            if any(keyword in script for keyword in MOTION_KEYWORDS):
                reason = ('임의 스크립트에 모션 명령이 있어 경로를 검사할 수 없습니다 — '
                          '안전 구역이 켜져 있어 거부합니다. line_cpp·line_relative 를 쓰십시오.')
                self._log(f'[안전구역] Raw Script 거부 — {reason}')
                return False, reason

        self._log(f"Raw Script: {script}")
        return self.gv_manager.send_script(script)
