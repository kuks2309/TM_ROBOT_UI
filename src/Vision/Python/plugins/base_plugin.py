"""비전 플러그인 공통 베이스 — initialize/process/cleanup 수명주기 계약(ABC)."""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import numpy as np


class BaseVisionPlugin(ABC):
    """비전 플러그인 베이스. 하위 클래스는 process 만 구현하면 된다."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._initialized = False

    def initialize(self, params: Optional[Dict[str, Any]] = None) -> bool:
        """플러그인 준비. params 는 하위 클래스 확장용 — 베이스는 무시하고 플래그만 세운다."""
        self._initialized = True
        return True

    @abstractmethod
    def process(self, image: np.ndarray, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """이미지 1장 처리. {'success','result_image','data','message'} 딕셔너리를 반환한다."""
        pass

    def cleanup(self) -> None:
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized
