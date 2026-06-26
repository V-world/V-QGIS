from typing import Any
from qgis.PyQt.QtCore import QSettings

from ..constants import (
    DEFAULT_PROTOCOL,
    PROTOCOL_OPTIONS,
    DEFAULT_TOOLBAR_DISPLAY_MODE,
    TOOLBAR_DISPLAY_MODES,
    DEFAULT_HEADER_STYLE,
    HEADER_STYLE_MODES,
)
from ..config import API_KEY  # config.py에서 API_KEY 가져오기


class ConfigManager:
    def __init__(self):
        self._settings = QSettings('VWorld', 'Plugin')

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
    def user_api_key(self) -> str:
        """
            사용자 API 키 반환 - config.py를 무시하고 QSettings에 저장된 키만 반환.
            엑셀 지오코딩 등 사용자 본인 키가 강제되는 기능에서 사용.
        """
        return self._settings.value('api_key', '') or ''

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

    @property
    def toolbar_display_mode(self) -> str:
        """
            툴바 표시 모드 식별자 반환 (TOOLBAR_DISPLAY_MODES 키)
        """
        value = self._settings.value('toolbar_display_mode', DEFAULT_TOOLBAR_DISPLAY_MODE)
        if value not in TOOLBAR_DISPLAY_MODES:
            return DEFAULT_TOOLBAR_DISPLAY_MODE
        return value

    @toolbar_display_mode.setter
    def toolbar_display_mode(self, value: str):
        """
            툴바 표시 모드 저장
        """
        if value not in TOOLBAR_DISPLAY_MODES:
            value = DEFAULT_TOOLBAR_DISPLAY_MODE
        self._settings.setValue('toolbar_display_mode', value)

    @property
    def header_style(self) -> str:
        """
            위젯 상단 브랜드 헤더 표시 모드 (HEADER_STYLE_MODES 키).
            standard=큰 헤더(기본값), compact=요약 헤더.
        """
        value = self._settings.value('header_style', DEFAULT_HEADER_STYLE)
        if value not in HEADER_STYLE_MODES:
            return DEFAULT_HEADER_STYLE
        return value

    @header_style.setter
    def header_style(self, value: str):
        """
            헤더 표시 모드 저장
        """
        if value not in HEADER_STYLE_MODES:
            value = DEFAULT_HEADER_STYLE
        self._settings.setValue('header_style', value)

    @property
    def show_success_popup(self) -> bool:
        """
            성공 안내 팝업(QMessageBox) 표시 여부.
            기본값 False — 성공은 무음(로그만)으로 처리해 캔버스를 방해하지 않는다.
            True로 켜면 작업 완료 시 차단 팝업으로 명확히 알린다(opt-in).
        """
        return self._settings.value('show_success_popup', False, type=bool)

    @show_success_popup.setter
    def show_success_popup(self, value: bool):
        """
            성공 안내 팝업 표시 여부 저장
        """
        self._settings.setValue('show_success_popup', bool(value))

    @property
    def notice_hide_until(self) -> str:
        """
            공지 팝업을 숨길 마지막 날짜 (YYYY-MM-DD).
            오늘 날짜가 이 값 이하이면 팝업을 띄우지 않는다.
        """
        return self._settings.value('notice_hide_until', '') or ''

    @notice_hide_until.setter
    def notice_hide_until(self, value: str):
        """
            공지 팝업 숨김 만료일 저장
        """
        self._settings.setValue('notice_hide_until', value)

    @property
    def onboarding_seen(self) -> bool:
        """
            '시작하기' 패널을 최초 1회 자동으로 띄웠는지 여부.
        """
        return self._settings.value('onboarding_seen', False, type=bool)

    @onboarding_seen.setter
    def onboarding_seen(self, value: bool):
        """
            '시작하기' 패널 자동 표시 완료 플래그 저장
        """
        self._settings.setValue('onboarding_seen', bool(value))

    @property
    def onboarding_hide(self) -> bool:
        """
            사용자가 '다음부터 표시하지 않기'를 선택했는지 여부.
        """
        return self._settings.value('onboarding_hide', False, type=bool)

    @onboarding_hide.setter
    def onboarding_hide(self, value: bool):
        """
            '시작하기' 패널 숨김 선택 저장
        """
        self._settings.setValue('onboarding_hide', bool(value))

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