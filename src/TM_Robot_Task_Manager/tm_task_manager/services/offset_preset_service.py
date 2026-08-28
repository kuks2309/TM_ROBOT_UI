"""평면 수직 정렬 그리퍼 오차 preset 저장소.

현장에서 그리퍼 오차는 공구를 바꾸거나 재장착할 때마다 다시 잡는다. 매번 6칸을
손으로 채우는 대신 이름을 붙여 저장해 두고 골라 쓰기 위한 파일 저장소다.

오차 축은 x, y, rx, ry, rz 5종이다 — 수직 정렬은 법선 방향 거리를 standoff_mm 이
정하므로 z 오차는 두지 않는다(jig_plane_calculator.TOOL_OFFSET_KEYS 와 같은 정의).

UI 는 본 서비스만 호출하고 파일을 직접 열지 않는다.
"""
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
        """정의된 축만 남기고 float 로 맞춘다. 없는 축은 0.0."""
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
        """preset 을 추가하거나 덮어쓴다. Returns: (ok, 사유)."""
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
