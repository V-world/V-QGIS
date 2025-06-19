import os
import json
from typing import Any, Optional
from PyQt5.QtCore import QSettings

from ..constants import OPTIONS_FILE, DEFAULT_PROTOCOL, PROTOCOL_OPTIONS
from ..config import API_KEY  # config.py에서 API_KEY 가져오기


class ConfigManager:
    def __init__(self):
        self._settings = QSettings('VWorld', 'Plugin')
        self._options = self._load_options()

    @property
    def api_key(self) -> str:
        """
            API 키 반환 - config.py의 값을 우선 사용
        """
        # config.py에 설정된 API_KEY가 있으면 그것을 사용
        if API_KEY:
            return API_KEY
        # 없으면 기존 설정에서 가져오기
        return self._settings.value('api_key', '')

    @api_key.setter
    def api_key(self, value: str):
        """
            API 키 설정 - config.py의 값이 있어도 설정은 저장
        """
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