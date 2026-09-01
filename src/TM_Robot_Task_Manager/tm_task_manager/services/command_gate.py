"""중복 명령 방지 게이트 — 점유 중 들어온 명령을 거부·카운트한다."""
from typing import Callable, Optional


class CommandGate:
    """busy 플래그 기반 명령 점유 게이트.

    락 없는 check-then-act 라 Qt 메인(GUI) 스레드 단일 호출 전제다 —
    현 호출자(JogService 등)는 전부 Qt 시그널 경유라 경합이 없다.
    """

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
        return self._rejected_count

    def acquire(self, label: str = "명령") -> bool:
        """점유를 시도한다 — 이미 점유 중이면 거부 수만 올리고 False."""
        if self._busy:
            self._rejected_count += 1
            return False

        self._busy = True
        self._current_label = label
        return True

    def release(self) -> None:
        """점유를 해제하고, 점유 중 버린 명령 수를 로그로 남긴다."""
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
        """acquire→func→finally release 래퍼 — 점유 실패 시 None."""
        if not self.acquire(label):
            return None

        try:
            return func(*args, **kwargs)
        finally:
            self.release()
