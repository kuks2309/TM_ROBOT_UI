"""조그 오케스트레이션 서비스.

조그 실행에 필요한 조립(이동 거리·속도 보유, 현재 TCP 자세 조회, 모션 콜백 전달)을
한곳에 모은다. 이 조립이 UI 클래스마다 복제되면 조그 진입점이 늘어날 때마다 같은
코드가 불어나므로, UI 는 축과 방향만 넘기고 나머지는 서비스가 책임진다.

실제 좌표 계산과 모션 발행은 TeachingService.jog_tcp / jog_tcp_continuous 가 그대로
담당한다 — 본 서비스는 그 앞단의 조립만 맡는다.
"""
from typing import Callable, List, Optional, Tuple

from PyQt5.QtCore import QObject, pyqtSignal

JOG_STEP_MM_DEFAULT = 10.0
JOG_VELOCITY_PERCENT_DEFAULT = 20


class JogService(QObject):
    # 성공 메시지는 TeachingService.jog_completed 가 이미 발신하므로 중복하지 않는다.
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
        """이동 거리·속도 갱신. 실제로 값이 바뀐 경우에만 params_changed 를 발신한다.

        여러 탭의 입력 위젯이 이 서비스를 공유하므로, 값이 같을 때도 발신하면
        위젯 → 서비스 → 위젯 순환으로 시그널이 되돈다.
        """
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
        if not self._teaching_service:
            return False, None, "TeachingService 가 초기화되지 않았습니다"
        if not self._move_callback:
            return False, None, "모션 콜백이 설정되지 않았습니다"

        pose = self._current_tcp_pose()
        if not pose:
            return False, None, "현재 로봇 위치를 알 수 없습니다"

        return True, pose, ""

    def _log_intent(self, kind: str, axis: str, direction: int) -> None:
        """어느 버튼이 눌렸는지 파일 로그에 남긴다 — 뒤따르는 `[모션]` 줄과 짝을 이룬다.

        `_call_set_positions` 의 `[모션]` 줄만으로는 목표 좌표만 보이고 어느 축 버튼이
        눌렸는지 알 수 없다. 조그가 의도치 않은 회전을 일으킨 건(2026-08-17) 조사용.
        """
        get_logger = getattr(self._ros_node, 'get_logger', None)
        if get_logger is None:
            return
        get_logger().info(
            f"[{kind}] axis={axis}{'+' if direction > 0 else '-'} "
            f"step={self._step_mm}mm vel={self._velocity_percent}%"
        )

    def _acquire(self, label: str) -> bool:
        """게이트가 없으면(단독 사용·테스트) 통과시킨다."""
        if self._command_gate is None:
            return True
        return self._command_gate.acquire(label)

    def _release(self) -> None:
        if self._command_gate is not None:
            self._command_gate.release()

    def jog(self, axis: str, direction: int) -> bool:
        """단발 조그(버튼용). 실패 시 jog_failed 로 사유를 알린다.

        모션이 끝날 때까지 GUI 가 블로킹되는 사이 쌓인 스팸 클릭은 게이트가 버린다.
        """
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
        """연속 조그(조이스틱용). 호출 빈도가 높아 실패는 조용히 무시하지 않고 알린다.

        주기 호출이라 명령이 가장 잘 쌓이는 경로다 — 앞 모션이 끝나기 전 들어온 호출은
        게이트가 버린다(스틱을 밀고 있어도 명령이 큐에 누적되지 않는다).
        """
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
