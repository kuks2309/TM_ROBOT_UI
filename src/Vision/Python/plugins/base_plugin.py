from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import numpy as np


class BaseVisionPlugin(ABC):
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._initialized = False

    def initialize(self, params: Optional[Dict[str, Any]] = None) -> bool:
        self._initialized = True
        return True

    @abstractmethod
    def process(self, image: np.ndarray, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pass

    def cleanup(self) -> None:
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized
