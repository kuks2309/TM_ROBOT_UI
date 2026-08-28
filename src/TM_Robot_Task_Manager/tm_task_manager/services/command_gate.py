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
        return self._rejected_count

    def acquire(self, label: str = "명령") -> bool:
        if self._busy:
            self._rejected_count += 1
            return False

        self._busy = True
        self._current_label = label
        return True

    def release(self) -> None:
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
        if not self.acquire(label):
            return None

        try:
            return func(*args, **kwargs)
        finally:
            self.release()
