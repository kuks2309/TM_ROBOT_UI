import os
import yaml
from typing import Any, Optional

from .. import paths


class ConfigManager:
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = paths.config('positions.yaml')
        self.config_path = os.path.abspath(config_path)
        self._config_cache: Optional[dict] = None

    def _load_config(self) -> dict:
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
