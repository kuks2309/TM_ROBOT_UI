import os
from typing import Dict, List, Optional, Tuple

import yaml

from ..tools.jig_plane_calculator import TOOL_OFFSET_KEYS

DEFAULT_PRESET_FILENAME = 'plane_align_offsets.yaml'


class OffsetPresetService:
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                '..', 'config', DEFAULT_PRESET_FILENAME
            )
        self.config_path = os.path.normpath(config_path)

    def _load_all(self) -> Dict[str, Dict[str, float]]:
        if not os.path.exists(self.config_path):
            return {}

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            return {}

        presets = data.get('presets')
        if not isinstance(presets, dict):
            return {}

        return {
            str(name): self._normalize(values)
            for name, values in presets.items()
            if isinstance(values, dict)
        }

    @staticmethod
    def _normalize(values: Dict) -> Dict[str, float]:
        normalized = {}
        for key in TOOL_OFFSET_KEYS:
            try:
                normalized[key] = float(values.get(key, 0.0))
            except (TypeError, ValueError):
                normalized[key] = 0.0
        return normalized

    def list_names(self) -> List[str]:
        return sorted(self._load_all().keys())

    def get(self, name: str) -> Optional[Dict[str, float]]:
        return self._load_all().get(name)

    def save(self, name: str, offset: Dict[str, float]) -> Tuple[bool, str]:
        name = (name or "").strip()
        if not name:
            return False, "preset 이름이 비어 있습니다"

        presets = self._load_all()
        existed = name in presets
        presets[name] = self._normalize(offset)

        ok, reason = self._write(presets)
        if not ok:
            return False, reason

        action = "덮어썼습니다" if existed else "저장했습니다"
        return True, f"오차 preset '{name}' 을(를) {action}"

    def delete(self, name: str) -> Tuple[bool, str]:
        presets = self._load_all()
        if name not in presets:
            return False, f"오차 preset '{name}' 이(가) 없습니다"

        del presets[name]
        ok, reason = self._write(presets)
        if not ok:
            return False, reason

        return True, f"오차 preset '{name}' 을(를) 삭제했습니다"

    def _write(self, presets: Dict[str, Dict[str, float]]) -> Tuple[bool, str]:
        try:
            directory = os.path.dirname(self.config_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump({'presets': presets}, f,
                               allow_unicode=True, sort_keys=True,
                               default_flow_style=False)
        except Exception as e:
            return False, f"오차 preset 파일 저장 실패: {e}"

        return True, ""
