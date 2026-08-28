from typing import Tuple, Callable, Optional, Sequence

MOTION_KEYWORDS = (
    'Line(', 'PTP(', 'Move_Line(', 'Move_PTP(', 'Vision_DoJob_PTP(', 'Circle(',
)


class TmRobotScriptMotion:
    """TMScript 로 나가는 모션. gateway 를 주면 안전 구역 사전 검사를 거친다."""

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
        """사전 검사. 관문이 없으면 통과시킨다(가드 미배선 환경 호환)."""
        if self._gateway is None:
            return True, ''
        decision = self._gateway.check(
            kind, target_mm=target_mm, offset_mm=offset_mm, label=label)
        if decision.allowed:
            return True, ''
        self._log(f'[안전구역] {label} 거부 — {decision.reason}')
        return False, decision.reason

    def change_base(self, base_name: str) -> Tuple[bool, str]:
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
        """임의 TMScript 전송 — 모션 명령이 섞여 있으면 안전 구역 활성 시 거부한다.

        목표를 파싱하지 않으므로 검사할 수 없다. 관문을 우회하는 구멍이 되지 않도록
        구역이 켜져 있는 동안은 모션 키워드가 보이면 막고, 전용 메서드를 쓰게 한다.
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
