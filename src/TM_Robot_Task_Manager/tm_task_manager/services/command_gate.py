"""수동·조그 명령 단일 실행 게이트.

로봇 명령은 GUI 스레드에서 동기 블로킹으로 모션 완료까지 기다린다
(main_window._send_set_positions). 그 대기 중 눌린 버튼은 Qt 이벤트 큐에 쌓이고,
로그 출력이 부르는 QApplication.processEvents() 가 그 큐를 재진입 실행시킨다.
그래서 스팸 클릭이 전부 기억됐다가 순서대로 실행된다 — 위험하다.

본 게이트는 "실행 중이면 새 명령을 받지 않는다"를 한곳에서 강제한다. 첫 명령만
실행되고 나머지는 그 자리에서 버려진다.

거부를 즉시 로그로 알리지 않는 이유: 로그 콜백이 processEvents() 를 부르므로
거부 로그가 다음 대기 클릭을 다시 배달해 재귀가 깊어진다. 그래서 무시한 건수만
세어 두었다가 해제 시점에 한 줄로 알린다.
"""
from typing import Callable, Optional


class CommandGate:
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        self._log_callback = log_callback
        self._busy = False
        self._current_label = ""
        self._rejected_count = 0

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def current_label(self) -> str:
        return self._current_label

    @property
    def rejected_count(self) -> int:
        """해제되면 0 으로 돌아간다. 테스트·진단용."""
        return self._rejected_count

    def acquire(self, label: str = "명령") -> bool:
        """실행 권한을 얻는다. 이미 실행 중이면 False (무시 건수만 증가)."""
        if self._busy:
            self._rejected_count += 1
            return False

        self._busy = True
        self._current_label = label
        return True

    def release(self) -> None:
        """실행을 끝낸다. 무시한 명령이 있었으면 한 줄로 알린다."""
        if not self._busy:
            return

        rejected = self._rejected_count
        label = self._current_label

        self._busy = False
        self._current_label = ""
        self._rejected_count = 0

        if rejected and self._log_callback:
            self._log_callback(
                f"[무시] '{label}' 실행 중 들어온 명령 {rejected}건을 버렸습니다 "
                f"(중복 실행 방지)"
            )

    def run(self, label: str, func: Callable, *args, **kwargs):
        """게이트를 잡고 func 를 실행한다. 거부되면 rejected_value 를 돌려준다.

        예외가 나도 게이트가 잠긴 채 남지 않도록 finally 로 해제한다 —
        한 번 잠긴 채 남으면 이후 모든 수동 명령이 죽는다.
        """
        if not self.acquire(label):
            return None

        try:
            return func(*args, **kwargs)
        finally:
            self.release()
