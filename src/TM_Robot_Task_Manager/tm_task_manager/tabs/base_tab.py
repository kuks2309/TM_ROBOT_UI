from typing import Callable, Optional


class BaseTab:
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
        """로그 위임. kind 는 «줄 때만» 넘긴다.

        _log(message) 한 개만 받는 구현(테스트 스텁·다른 창)이 있어서, 항상
        두 인자로 부르면 그쪽이 TypeError 로 죽는다. 판정을 명시할 때만
        확장 시그니처를 쓰고 평소에는 기존 호출 형태를 유지한다.
        """
        if kind is None:
            self.main_window._log(message)
        else:
            self.main_window._log(message, kind)

    def connect_signals(self):
        raise NotImplementedError

    def init_ui(self):
        pass
