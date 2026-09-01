"""positions.yaml 설정 접근자 — 로봇 IP·등록 자세·점 표기 키 경로의 읽기/쓰기."""
import os
import yaml
from typing import Any, List, Optional

from .. import paths


class ConfigManager:
    """positions.yaml 캐시 로더.

    캐시는 인스턴스 단위다 — 인스턴스를 여러 곳에서 만들면 한쪽의 저장이
    다른 쪽 캐시에 보이지 않는다(공유하려면 같은 인스턴스를 주입할 것).
    """

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = paths.config('positions.yaml')
        self.config_path = os.path.abspath(config_path)
        self._config_cache: Optional[dict] = None

    def _load_config(self) -> dict:
        # 최초 1회만 디스크에서 읽음 — 외부에서 파일이 바뀌면 reload() 필요
        if self._config_cache is None:
            if not os.path.exists(self.config_path):
                self._config_cache = {}
            else:
                try:
                    with open(self.config_path, 'r', encoding='utf-8') as f:
                        self._config_cache = yaml.safe_load(f) or {}
                except Exception as e:
                    print(f"ConfigManager: 설정 파일 로드 실패: {e}")
                    self._config_cache = {}
        return self._config_cache

    def _save_config(self, config: dict):
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

            self._config_cache = config
        except Exception as e:
            print(f"ConfigManager: 설정 파일 저장 실패: {e}")
            raise

    def reload(self):
        """캐시를 버리고 디스크에서 다시 읽는다."""
        self._config_cache = None
        return self._load_config()

    def get_config_path(self) -> str:
        return self.config_path

    def get_robot_ip(self) -> Optional[str]:
        config = self._load_config()
        return config.get('robot', {}).get('ip')

    def set_robot_ip(self, ip: str):
        config = self._load_config()
        if 'robot' not in config:
            config['robot'] = {}
        config['robot']['ip'] = ip
        self._save_config(config)

    def get_position(self, name: str) -> Optional[dict]:
        """등록 자세 1건 조회 — {'type': joint|tcp, 'values': [6개]} 형태, 없으면 None."""
        config = self._load_config()
        return (config.get('positions') or {}).get(name)

    def get_position_names(self) -> List[str]:
        """등록 자세 이름 목록(사전순 정렬)."""
        config = self._load_config()
        return sorted((config.get('positions') or {}).keys())

    def get_home_position(self) -> Optional[dict]:
        config = self._load_config()
        return config.get('positions', {}).get('home')

    def set_home_position(self, values: dict):
        config = self._load_config()
        if 'positions' not in config:
            config['positions'] = {}
        if 'home' not in config['positions']:
            config['positions']['home'] = {}

        config['positions']['home']['values'] = values

        self._save_config(config)

    def get(self, key_path: str, default: Any = None) -> Any:
        """점 표기 경로 조회 (예: 'robot.ip') — 경로 중간이 없으면 default."""
        config = self._load_config()
        keys = key_path.split('.')
        value = config

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default

        return value

    def set(self, key_path: str, value: Any):
        """점 표기 경로에 값 기록 — 중간 dict 를 만들어 가며 즉시 파일 저장."""
        config = self._load_config()
        keys = key_path.split('.')
        target = config

        for key in keys[:-1]:
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
            target = target[key]

        target[keys[-1]] = value

        self._save_config(config)

    def delete(self, key_path: str) -> bool:
        config = self._load_config()
        keys = key_path.split('.')
        target = config

        for key in keys[:-1]:
            if not isinstance(target, dict) or key not in target:
                return False
            target = target[key]

        if isinstance(target, dict) and keys[-1] in target:
            del target[keys[-1]]
            self._save_config(config)
            return True

        return False

    def get_all(self) -> dict:
        config = self._load_config()
        return config.copy()
