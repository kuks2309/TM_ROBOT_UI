"""조그 파사드 — 파라미터 보관 + CommandGate 점유 하에 TeachingService 로 위임."""
from typing import Callable, List, Optional, Tuple

from PyQt5.QtCore import QObject, pyqtSignal

JOG_STEP_MM_DEFAULT = 10.0
JOG_VELOCITY_PERCENT_DEFAULT = 20


class JogService(QObject):
    """키보드 탭·조이스틱이 함께 쓰는 조그 공용 진입점 (Qt 메인 스레드 전제).

    step(mm)·velocity(%) 를 보관하고, CommandGate 로 중복 실행을 막은 뒤
    TeachingService.jog_tcp(_continuous) 에 위임한다. 실패는 jog_failed 시그널.
    """

    jog_failed = pyqtSignal(str)
    params_changed = pyqtSignal(float, int)

    def __init__(self, ros_node=None, teaching_service=None,
                 move_callback: Optional[Callable] = None, command_gate=None):
        super().__init__()
        self._ros_node = ros_node
        self._teaching_service = teaching_service
        self._move_callback = move_callback
        self._command_gate = command_gate

        self._step_mm = JOG_STEP_MM_DEFAULT
        self._velocity_percent = JOG_VELOCITY_PERCENT_DEFAULT

    def set_ros_node(self, ros_node):
        self._ros_node = ros_node

    def set_move_callback(self, move_callback: Callable):
        self._move_callback = move_callback

    def get_params(self) -> Tuple[float, int]:
        return self._step_mm, self._velocity_percent

    def set_params(self, step_mm: Optional[float] = None,
                   velocity_percent: Optional[int] = None) -> bool:
        """조그 스텝(mm)/속도(%)를 갱신한다 — 값이 실제로 바뀐 경우만 시그널."""
        changed = False

        if step_mm is not None and float(step_mm) != self._step_mm:
            self._step_mm = float(step_mm)
            changed = True

        if velocity_percent is not None and int(velocity_percent) != self._velocity_percent:
            self._velocity_percent = int(velocity_percent)
            changed = True

        if changed:
            self.params_changed.emit(self._step_mm, self._velocity_percent)

        return changed

    def _current_tcp_pose(self) -> Optional[List[float]]:
        if not self._ros_node:
            return None
        return getattr(self._ros_node, 'current_tcp_pose', None)

    def _prepare(self) -> Tuple[bool, Optional[List[float]], str]:
        """의존성·현재 TCP 존재를 사전 점검한다 — (가능 여부, pose, 오류 문구)."""
        if not self._teaching_service:
            return False, None, "TeachingService 가 초기화되지 않았습니다"
        if not self._move_callback:
            return False, None, "모션 콜백이 설정되지 않았습니다"

        pose = self._current_tcp_pose()
        if not pose:
            return False, None, "현재 로봇 위치를 알 수 없습니다"

        return True, pose, ""

    def _log_intent(self, kind: str, axis: str, direction: int) -> None:
        get_logger = getattr(self._ros_node, 'get_logger', None)
        if get_logger is None:
            return
        get_logger().info(
            f"[{kind}] axis={axis}{'+' if direction > 0 else '-'} "
            f"step={self._step_mm}mm vel={self._velocity_percent}%"
        )

    def _acquire(self, label: str) -> bool:
        if self._command_gate is None:
            return True
        return self._command_gate.acquire(label)

    def _release(self) -> None:
        if self._command_gate is not None:
            self._command_gate.release()

    def jog(self, axis: str, direction: int) -> bool:
        """단발 조그 — 게이트 점유 실패(다른 명령 실행 중)면 조용히 False."""
        if not self._acquire(f"조그 {axis}{'+' if direction > 0 else '-'}"):
            return False

        try:
            return self._jog(axis, direction)
        finally:
            self._release()

    def _jog(self, axis: str, direction: int) -> bool:
        self._log_intent('조그', axis, direction)
        ok, pose, err = self._prepare()
        if not ok:
            self.jog_failed.emit(err)
            return False

        success, msg = self._teaching_service.jog_tcp(
            axis, direction, self._step_mm, float(self._velocity_percent),
            pose, list(pose[3:6]), self._move_callback
        )
        if not success:
            self.jog_failed.emit(msg)
        return success

    def jog_continuous(self, axis: str, direction: int) -> bool:
        """연속 조그(레이트리밋 없는 반복 호출용) — 점유 실패 시 False."""
        if not self._acquire(f"연속 조그 {axis}{'+' if direction > 0 else '-'}"):
            return False

        try:
            return self._jog_continuous(axis, direction)
        finally:
            self._release()

    def _jog_continuous(self, axis: str, direction: int) -> bool:
        self._log_intent('연속 조그', axis, direction)
        ok, pose, err = self._prepare()
        if not ok:
            self.jog_failed.emit(err)
            return False

        success, msg = self._teaching_service.jog_tcp_continuous(
            axis, direction, self._step_mm, float(self._velocity_percent),
            pose, list(pose[3:6]), self._move_callback
        )
        if not success:
            self.jog_failed.emit(msg)
        return success
