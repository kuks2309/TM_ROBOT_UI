"""Vision/Python/plugins 디렉토리의 비전 플러그인 동적 로더 (모듈 싱글턴)."""
import os
import sys
import importlib
import importlib.util
from typing import Dict, List, Any, Optional
from pathlib import Path

# import 부수효과: base_plugin(`from plugins...`)을 찾을 수 있게 Vision/Python 을
# sys.path 맨 앞에 넣는다 — 프로세스 전역 해석 순서가 바뀌는 점에 유의
VISION_PYTHON_PATH = Path(__file__).parent.parent.parent.parent.parent / 'Vision' / 'Python'
if str(VISION_PYTHON_PATH) not in sys.path:
    sys.path.insert(0, str(VISION_PYTHON_PATH))


class VisionPluginManager:
    """plugins/*.py 를 spec 로드해 BaseVisionPlugin 서브클래스를 이름으로 등록한다."""

    def __init__(self):
        self._plugins: Dict[str, Any] = {}
        self._plugins_path = VISION_PYTHON_PATH / 'plugins'
        self._loaded = False

    def load_plugins(self) -> None:
        """플러그인 폴더를 1회 순회 로드한다 — 개별 실패는 로그만 남기고 계속."""
        if self._loaded:
            return

        if not self._plugins_path.exists():
            print(f"[VisionPluginManager] 플러그인 폴더가 없습니다: {self._plugins_path}")
            return

        for plugin_file in self._plugins_path.glob('*.py'):
            if plugin_file.name in ('__init__.py', 'base_plugin.py'):
                continue

            plugin_name = plugin_file.stem
            try:
                self._load_plugin(plugin_name, plugin_file)
            except Exception as e:
                print(f"[VisionPluginManager] 플러그인 로드 실패 ({plugin_name}): {e}")

        self._loaded = True
        print(f"[VisionPluginManager] {len(self._plugins)}개 플러그인 로드 완료")

    def _load_plugin(self, name: str, path: Path) -> None:
        """파일 하나를 exec 해 첫 BaseVisionPlugin 서브클래스만 인스턴스화·등록한다.

        모듈은 무접두 이름으로 sys.modules 에 올라간다 — 표준 모듈과 이름이
        겹치는 플러그인 파일명은 피할 것.
        """
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"모듈 스펙을 로드할 수 없습니다: {path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)

        from plugins.base_plugin import BaseVisionPlugin

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and
                issubclass(attr, BaseVisionPlugin) and
                attr is not BaseVisionPlugin):
                plugin_instance = attr()
                self._plugins[plugin_instance.name] = plugin_instance
                print(f"[VisionPluginManager] 플러그인 로드: {plugin_instance.name}")
                break

    def get_plugin(self, name: str) -> Optional[Any]:
        """이름으로 플러그인 인스턴스 조회 (첫 호출 시 지연 로드)."""
        if not self._loaded:
            self.load_plugins()
        return self._plugins.get(name)

    def get_available_plugins(self) -> List[str]:
        if not self._loaded:
            self.load_plugins()
        return list(self._plugins.keys())

    def get_plugin_info(self, name: str) -> Optional[Dict[str, Any]]:
        plugin = self.get_plugin(name)
        if plugin is None:
            return None
        return {
            'name': plugin.name,
            'description': plugin.description,
            'initialized': plugin.is_initialized
        }

    def reload_plugins(self) -> None:
        """등록을 비우고 폴더를 다시 로드한다 (플러그인 파일 갱신 반영용)."""
        self._plugins.clear()
        self._loaded = False
        self.load_plugins()


_instance: Optional[VisionPluginManager] = None


def get_vision_plugin_manager() -> VisionPluginManager:
    """모듈 싱글턴 접근자 — 락 없는 check-then-act 라 첫 호출은 단일 스레드 전제."""
    global _instance
    if _instance is None:
        _instance = VisionPluginManager()
    return _instance
