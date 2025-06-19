import os
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
import logging

from .base_widget import BaseDialog
from ..constants import UI_DIR, PROTOCOL_OPTIONS
from ..utils import ConfigManager, Validators, with_error_handling

logger = logging.getLogger(__name__)

FORM_CLASS, _ = uic.loadUiType(os.path.join(UI_DIR, 'v_world_setting_base.ui'))


class SettingsWidget(BaseDialog, FORM_CLASS):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.config = ConfigManager()
        self._load_settings()
        self._connect_signals()

    def _load_settings(self):
        """
            현재 설정 로드
        """
        # API 키
        self.APIKey.setText(self.config.api_key)

        # 프로토콜
        protocol_name = self.config.get('protocol', 'HTTPS(기본값)')
        if protocol_name == 'HTTP':
            self.HTTP.setChecked(True)
        elif protocol_name == 'HTTPS(보안무시)':
            self.HTTPSX.setChecked(True)
        else:
            self.HTTPS.setChecked(True)

        # 라벨 스타일
        if self.config.land_label_style:
            self.landLabelSytleON.setChecked(True)
        else:
            self.landLabelSytleOFF.setChecked(True)

    def _connect_signals(self):
        """
            시그널 연결
        """
        # API 키
        self.APIKey.editingFinished.connect(self._save_api_key)

        # 프로토콜
        self.HTTP.clicked.connect(lambda: self._save_protocol('HTTP'))
        self.HTTPS.clicked.connect(lambda: self._save_protocol('HTTPS(기본값)'))
        self.HTTPSX.clicked.connect(lambda: self._save_protocol('HTTPS(보안무시)'))

        # 라벨 스타일
        self.landLabelSytleON.clicked.connect(lambda: self._save_label_style(True))
        self.landLabelSytleOFF.clicked.connect(lambda: self._save_label_style(False))

    @with_error_handling("API 키 저장 중 오류가 발생했습니다")
    def _save_api_key(self):
        """
            API 키 저장
        """
        api_key = self.APIKey.text().strip()

        if api_key and not Validators.validate_api_key(api_key):
            self.show_warning_message("경고", "유효하지 않은 API 키 형식입니다.")
            return

        self.config.api_key = api_key
        self.APIKey.setText(api_key)

        if api_key:
            self.show_info_message("저장 완료", "API 키가 저장되었습니다.")

        logger.info("API 키 저장됨")

    def _save_protocol(self, protocol: str):
        """
            프로토콜 저장
        """
        try:
            self.config.protocol = protocol
            self.show_info_message("저장 완료", "프로토콜 설정이 저장되었습니다.")
            logger.info(f"프로토콜 변경: {protocol}")
        except Exception as e:
            logger.error(f"프로토콜 저장 실패: {e}")
            self.show_error_message("오류", "프로토콜 저장에 실패했습니다.")

    def _save_label_style(self, enabled: bool):
        """
            라벨 스타일 저장
        """
        try:
            self.config.land_label_style = enabled
            status = "활성화" if enabled else "비활성화"
            self.show_info_message("저장 완료", f"토지 라벨 표시가 {status}되었습니다.")
            logger.info(f"토지 라벨 스타일: {enabled}")
        except Exception as e:
            logger.error(f"라벨 스타일 저장 실패: {e}")
            self.show_error_message("오류", "라벨 스타일 저장에 실패했습니다.")