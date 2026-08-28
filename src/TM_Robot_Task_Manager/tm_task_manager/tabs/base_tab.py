"""모든 탭의 공통 베이스 — main_window 참조 하나로 서비스·매니저 접근을 위임한다."""
from typing import Callable, Optional


class BaseTab:
    """탭 공통 베이스. 서비스 접근 property 위임·로그 위임과 탭 수명주기 훅(connect_signals/init_ui)을 제공한다."""

    def __init__(self, main_window):
        self.main_window = main_window

    @property
    def ros_node(self):
        return self.main_window.ros_node

    @property
    def recipe_manager(self):
        return self.main_window.recipe_manager

    @property
    def job_executor(self):
        return self.main_window.job_executor

    @property
    def vision_manager(self):
        return self.main_window.vision_manager

    @property
    def gv_manager(self):
        return self.main_window.gv_manager

    @property
    def config_manager(self):
        return self.main_window.config_manager

    def _log(self, message: str, kind=None):
        if kind is None:
            self.main_window._log(message)
        else:
            self.main_window._log(message, kind)

    def connect_signals(self):
        """탭별 시그널/슬롯 연결 지점 — 파생 탭이 반드시 구현한다."""
        raise NotImplementedError

    def init_ui(self):
        """탭별 UI 초기화 지점 — 기본은 no-op(초기화가 필요 없는 탭용)."""
        pass
