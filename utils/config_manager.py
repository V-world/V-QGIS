import os
import json
from typing import Any, Optional
from PyQt5.QtCore import QSettings

from ..constants import OPTIONS_FILE, DEFAULT_PROTOCOL, PROTOCOL_OPTIONS, ENV_FILE
from ..config import API_KEY  # config.py에서 기본 API_KEY 가져오기


class ConfigManager:
    def __init__(self):
        self._settings = QSettings('VWorld', 'Plugin')
        self._options = self._load_options()
        self._env_cache = None  # .env 파일 캐시

    def _load_env(self) -> dict:
        """
            .env 파일 로드 (캐싱)
        """
        if self._env_cache is None:
            from .file_manager import FileManager
            self._env_cache = FileManager.read_env(ENV_FILE)
        return self._env_cache

    def _reload_env(self) -> dict:
        """
            .env 파일 강제 리로드
        """
        self._env_cache = None
        return self._load_env()

    @property
    def api_key(self) -> str:
        """
            API 키 반환

            우선순위:
            1. .env 파일의 VWORLD_API_KEY (사용자 커스텀)
            2. config.py의 API_KEY (기본 공용 키)
            3. QSettings에 저장된 키 (레거시)
        """
        # 1순위: .env 파일
        env_vars = self._load_env()
        env_api_key = env_vars.get('VWORLD_API_KEY', '').strip()
        if env_api_key:
            return env_api_key

        # 2순위: config.py의 기본 키
        if API_KEY:
            return API_KEY

        # 3순위: 기존 설정 (레거시)
        return self._settings.value('api_key', '')

    @api_key.setter
    def api_key(self, value: str):
        """
            API 키 설정 - .env 파일에 저장

            Args:
                value: API 키 값
        """
        from .file_manager import FileManager

        if value and value.strip():
            # .env 파일에 저장
            FileManager.update_env_variable(ENV_FILE, 'VWORLD_API_KEY', value.strip())
            # 캐시 갱신
            self._reload_env()

        # 레거시 지원: QSettings에도 저장
        self._settings.setValue('api_key', value)

    @property
    def protocol(self) -> tuple:
        """
            프로토콜 반환
        """
        protocol_name = self._settings.value('protocol', 'HTTPS(기본값)')
        return PROTOCOL_OPTIONS.get(protocol_name, (DEFAULT_PROTOCOL, True))

    @protocol.setter
    def protocol(self, value: str):
        """
            프로토콜 설정
        """
        self._settings.setValue('protocol', value)

    @property
    def land_label_style(self) -> bool:
        """
            토지 라벨 스타일 반환
        """
        return self._settings.value('land_label_style', True, type=bool)

    @land_label_style.setter
    def land_label_style(self, value: bool):
        """
            토지 라벨 스타일 설정
        """
        self._settings.setValue('land_label_style', value)

    def _load_options(self) -> dict:
        """
            옵션 파일 로드
        """
        if os.path.exists(OPTIONS_FILE):
            try:
                with open(OPTIONS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def get(self, key: str, default: Any = None) -> Any:
        """
            설정 값 가져오기
        """
        return self._settings.value(key, default)

    def set(self, key: str, value: Any):
        """
            설정 값 저장
        """
        self._settings.setValue(key, value)