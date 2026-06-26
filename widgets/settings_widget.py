import logging
from datetime import date

from qgis.PyQt.QtCore import Qt, QEvent, QTimer, QUrl, QSize, QStandardPaths, pyqtSignal
from qgis.PyQt.QtGui import QDesktopServices, QIcon
from qgis.PyQt.QtWidgets import (
    QLineEdit, QListWidgetItem, QListWidget, QStackedWidget, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, QToolButton, QPushButton,
    QRadioButton, QGroupBox, QGridLayout, QCheckBox, QFileDialog,
)

from .base_widget import BaseDialog
from ..constants import (
    UI_TEXTS,
    TOOLBAR_DISPLAY_MODES,
    DEFAULT_TOOLBAR_DISPLAY_MODE,
    HEADER_STYLE_STANDARD,
    HEADER_STYLE_COMPACT,
)
from ..utils import (
    ConfigManager, Validators, with_error_handling, ThemeColors, export_logs,
)

logger = logging.getLogger(__name__)

_STATUS_FADE_MS = 3000

_NAV_QSS = """QListWidget {
    background: palette(window);
    border: none;
    border-right: 1px solid palette(mid);
    padding: 12px 4px;
    outline: 0;
}
QListWidget::item {
    padding: 8px 12px;
    border-radius: 4px;
    color: palette(window-text);
}
QListWidget::item:hover {
    background: palette(light);
}
QListWidget::item:selected {
    background: palette(highlight);
    color: palette(highlighted-text);
}"""

_STACK_QSS = """QStackedWidget > QWidget {
    background: palette(base);
}"""


def _hline() -> QFrame:
    """수평 구분선 (이전 .ui의 Line 위젯 대체)."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


def _status_color(level: str) -> str:
    if level == 'warn':
        return ThemeColors.status_warn()
    if level == 'error':
        return ThemeColors.status_error()
    return ThemeColors.status_info()

_NAV_ITEMS = [
    ('settings_page_general', ':/icon_setting'),
    ('settings_page_network', ':/icon_layer'),
    ('settings_page_display', ':/icon_styleChange'),
    ('settings_page_about',   ':/icon_languages'),
]

_TB_RADIO_KEYS = {
    'tbStyleBesideIcon': 'TextBesideIcon',
    'tbStyleUnderIcon':  'TextUnderIcon',
    'tbStyleIconOnly':   'IconOnly',
    'tbStyleTextOnly':   'TextOnly',
}


class SettingsWidget(BaseDialog):

    toolbarStyleChanged = pyqtSignal(str)
    headerStyleChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.config = ConfigManager()

        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self._clear_status)

        self._setup_navigation()
        self._apply_theme_text()
        self._load_settings()
        self._connect_signals()

        # 포커스 기반 echo 모드 자동 토글
        self.APIKey.installEventFilter(self)

    def _build_ui(self):
        """코드로 UI 구성 (이전 v_world_setting_base.ui 대체)."""
        self.setWindowTitle("옵션")
        self.setMinimumSize(680, 460)
        self.resize(720, 500)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        content = QHBoxLayout()
        content.setSpacing(0)

        # 좌측 내비게이션
        self.navList = QListWidget()
        self.navList.setMinimumSize(160, 0)
        self.navList.setMaximumWidth(160)
        self.navList.setFrameShape(QFrame.Shape.NoFrame)
        self.navList.setSpacing(4)
        self.navList.setIconSize(QSize(18, 18))
        self.navList.setStyleSheet(_NAV_QSS)
        content.addWidget(self.navList)

        # 우측 페이지 스택
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(_STACK_QSS)
        self.stack.addWidget(self._build_page_general())
        self.stack.addWidget(self._build_page_network())
        self.stack.addWidget(self._build_page_display())
        self.stack.addWidget(self._build_page_about())
        content.addWidget(self.stack)

        root.addLayout(content)

        # 푸터
        root.addWidget(_hline())
        footer = QHBoxLayout()
        footer.setContentsMargins(16, 10, 16, 10)
        self.statusLabel = QLabel("")
        self.statusLabel.setMinimumHeight(20)
        footer.addWidget(self.statusLabel)
        footer.addStretch(1)
        self.closeBtn = QPushButton("닫기")
        self.closeBtn.setDefault(True)
        footer.addWidget(self.closeBtn)
        root.addLayout(footer)

    @staticmethod
    def _page_layout(page: QWidget) -> QVBoxLayout:
        """페이지 공통 여백/간격을 가진 QVBoxLayout 생성."""
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        return layout

    def _build_page_general(self) -> QWidget:
        page = QWidget()
        layout = self._page_layout(page)

        self.pageGeneralTitle = self.make_section_title("일반")
        layout.addWidget(self.pageGeneralTitle)
        self.pageGeneralSubtitle = QLabel("브이월드 API 인증키를 관리합니다.")
        layout.addWidget(self.pageGeneralSubtitle)
        layout.addWidget(_hline())

        self.apiKeyHint = QLabel()
        self.apiKeyHint.setWordWrap(True)
        layout.addWidget(self.apiKeyHint)

        self.apiKeyLabel = QLabel("API 인증키")
        layout.addWidget(self.apiKeyLabel)

        api_key_row = QHBoxLayout()
        api_key_row.setSpacing(6)
        self.APIKey = QLineEdit()
        self.APIKey.setEchoMode(QLineEdit.EchoMode.Password)
        self.APIKey.setPlaceholderText(
            "인증키를 입력하세요 (ex AAAA-AAAAAAAA-AAAAAAAA-AAAA)"
        )
        self.APIKey.setClearButtonEnabled(True)
        api_key_row.addWidget(self.APIKey)
        self.togglePwBtn = QToolButton()
        self.togglePwBtn.setText("표시")
        self.togglePwBtn.setCheckable(True)
        self.togglePwBtn.setToolTip("인증키 표시/숨김")
        self.togglePwBtn.setMinimumSize(48, 0)
        api_key_row.addWidget(self.togglePwBtn)
        layout.addLayout(api_key_row)

        actions_row = QHBoxLayout()
        self.openVworldBtn = QPushButton("V-World에서 인증키 발급받기")
        self.openVworldBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        actions_row.addWidget(self.openVworldBtn)
        actions_row.addStretch(1)
        layout.addLayout(actions_row)

        layout.addStretch(1)
        return page

    def _build_page_network(self) -> QWidget:
        page = QWidget()
        layout = self._page_layout(page)

        self.pageNetworkTitle = self.make_section_title("네트워크")
        layout.addWidget(self.pageNetworkTitle)
        self.pageNetworkSubtitle = QLabel(
            "브이월드 서버 호출에 사용할 프로토콜을 선택합니다."
        )
        layout.addWidget(self.pageNetworkSubtitle)
        layout.addWidget(_hline())

        self.HTTPS = QRadioButton("HTTPS (기본값)")
        self.HTTPS.setToolTip("인증서 검증 포함 - 권장")
        self.HTTPS.setChecked(True)
        layout.addWidget(self.HTTPS)
        self.HTTPSX = QRadioButton("HTTPS (보안 무시)")
        self.HTTPSX.setToolTip(
            "SSL 검증을 건너뜁니다. 사내망/프록시 환경 등에서만 사용하세요."
        )
        layout.addWidget(self.HTTPSX)
        # 보안 무시 선택 시에만 보이는 상시 경고 (저장된 설정에도 _load_settings에서 반영)
        self.protocolWarnLabel = QLabel(
            "⚠ 'HTTPS (보안 무시)'는 서버 인증서를 확인하지 않아 통신 내용이 "
            "위·변조(중간자 공격)될 수 있습니다.\n"
            "사내망 보안장비·프록시 때문에 기본 HTTPS 연결이 실패하는 경우에만 "
            "임시로 사용하고, 가능해지면 다시 'HTTPS (기본값)'으로 되돌려 주세요."
        )
        self.protocolWarnLabel.setWordWrap(True)
        self.protocolWarnLabel.setStyleSheet("color: #b35900;")  # 경고 주황
        self.protocolWarnLabel.setVisible(False)
        layout.addWidget(self.protocolWarnLabel)
        self.HTTP = QRadioButton("HTTP")
        self.HTTP.setToolTip(
            "암호화되지 않은 통신. HTTPS가 차단된 환경에서만 사용하세요."
        )
        layout.addWidget(self.HTTP)

        layout.addStretch(1)
        return page

    def _build_page_display(self) -> QWidget:
        page = QWidget()
        layout = self._page_layout(page)

        self.pageDisplayTitle = self.make_section_title("화면 표시")
        layout.addWidget(self.pageDisplayTitle)
        self.pageDisplaySubtitle = QLabel(
            "지적도 라벨과 툴바 표시 방식을 설정합니다."
        )
        layout.addWidget(self.pageDisplaySubtitle)
        layout.addWidget(_hline())

        # 지적도 라벨 그룹
        self.labelGroup = QGroupBox("지적도 라벨 및 스타일 자동적용")
        label_layout = QVBoxLayout(self.labelGroup)
        self.landLabelSytleON = QRadioButton("지적도 라벨 적용 (기본값)")
        self.landLabelSytleON.setChecked(True)
        label_layout.addWidget(self.landLabelSytleON)
        self.landLabelSytleOFF = QRadioButton("지적도 라벨 미적용")
        label_layout.addWidget(self.landLabelSytleOFF)
        layout.addWidget(self.labelGroup)

        # 헤더(패널 상단 파란 영역) 표시 모드 그룹
        self.headerStyleGroup = QGroupBox("패널 헤더 표시 모드")
        header_layout = QVBoxLayout(self.headerStyleGroup)
        self.headerStyleStandard = QRadioButton("표준 (큰 헤더)")
        self.headerStyleStandard.setToolTip(
            "각 패널 상단에 아이콘·제목·설명을 담은 큰 파란 헤더를 표시합니다 (기본값)."
        )
        self.headerStyleStandard.setChecked(True)
        header_layout.addWidget(self.headerStyleStandard)
        self.headerStyleCompact = QRadioButton("요약 (간단한 헤더)")
        self.headerStyleCompact.setToolTip(
            "헤더를 얇게 줄이고 설명 문구를 숨겨 작업 공간을 넓게 씁니다."
        )
        header_layout.addWidget(self.headerStyleCompact)
        layout.addWidget(self.headerStyleGroup)

        # 툴바 표시 모드 그룹
        self.toolbarStyleGroup = QGroupBox("툴바 표시 모드")
        tb_layout = QGridLayout(self.toolbarStyleGroup)
        tb_layout.setHorizontalSpacing(16)
        tb_layout.setVerticalSpacing(8)
        self.tbStyleBesideIcon = QRadioButton("아이콘 + 텍스트 (오른쪽)")
        self.tbStyleUnderIcon = QRadioButton("아이콘 + 텍스트 (아래)")
        self.tbStyleIconOnly = QRadioButton("아이콘만")
        self.tbStyleTextOnly = QRadioButton("텍스트만")
        tb_layout.addWidget(self.tbStyleBesideIcon, 0, 0)
        tb_layout.addWidget(self.tbStyleUnderIcon, 0, 1)
        tb_layout.addWidget(self.tbStyleIconOnly, 1, 0)
        tb_layout.addWidget(self.tbStyleTextOnly, 1, 1)
        layout.addWidget(self.toolbarStyleGroup)

        # 알림 그룹
        self.notificationGroup = QGroupBox("알림")
        noti_layout = QVBoxLayout(self.notificationGroup)
        self.showSuccessPopupCheck = QCheckBox("작업 완료 시 팝업으로 알림")
        self.showSuccessPopupCheck.setToolTip(
            "기본값은 꺼짐 — 레이어 추가/지오코딩 완료 등은 조용히 처리됩니다.\n"
            "켜면 작업이 끝날 때마다 팝업으로 명확히 알립니다.\n"
            "(오류·경고는 이 설정과 무관하게 항상 팝업으로 표시됩니다)"
        )
        self.showSuccessPopupCheck.setChecked(False)
        noti_layout.addWidget(self.showSuccessPopupCheck)
        layout.addWidget(self.notificationGroup)

        layout.addStretch(1)
        return page

    def _build_page_about(self) -> QWidget:
        page = QWidget()
        layout = self._page_layout(page)

        self.pageAboutTitle = self.make_section_title("정보")
        layout.addWidget(self.pageAboutTitle)
        layout.addWidget(_hline())

        self.aboutBody = QLabel()
        self.aboutBody.setOpenExternalLinks(True)
        self.aboutBody.setWordWrap(True)
        layout.addWidget(self.aboutBody)

        # 문제 해결 - 로그 파일 내보내기
        layout.addWidget(_hline())
        self.troubleshootTitle = self.make_section_title("문제 해결")
        layout.addWidget(self.troubleshootTitle)
        self.troubleshootHint = QLabel()
        self.troubleshootHint.setWordWrap(True)
        layout.addWidget(self.troubleshootHint)

        log_row = QHBoxLayout()
        self.saveLogBtn = QPushButton("로그 파일 저장…")
        self.saveLogBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        log_row.addWidget(self.saveLogBtn)
        log_row.addStretch(1)
        layout.addLayout(log_row)

        layout.addStretch(1)
        return page

    def _apply_theme_text(self):
        """
            팔레트(라이트/다크)에 맞춰 안내·캡션 텍스트 색상 재적용.
            .ui 파일의 inline HTML 색상이 다크 테마에서 안 보이는 문제를 우회.
        """
        muted = ThemeColors.muted()
        warning = ThemeColors.warning()
        link = ThemeColors.link()

        self.pageGeneralSubtitle.setText(
            f'<span style="color:{muted};">브이월드 API 인증키를 관리합니다.</span>'
        )
        self.pageNetworkSubtitle.setText(
            f'<span style="color:{muted};">브이월드 서버 호출에 사용할 프로토콜을 선택합니다.</span>'
        )
        self.pageDisplaySubtitle.setText(
            f'<span style="color:{muted};">지적도 라벨, 패널 헤더, 툴바 표시 방식, 알림 동작을 설정합니다.</span>'
        )
        self.apiKeyHint.setText(
            '<html><body><p>인증키 발급 시 서비스 유형은 <b>\'기타\'</b>로 선택하세요.'
            '<br/>'
            f'<span style=" font-size:8pt; color:{warning};">'
            '(지오코딩 외 기능 이용 시 필수사항이 아닙니다)</span></p></body></html>'
        )
        self.aboutBody.setText(
            '<html><body>'
            '<p><b>V-QGIS</b> — 공간정보 오픈플랫폼(브이월드) 플러그인</p>'
            '<p>V-World API 키는 '
            f'<a style="color:{link};" href="https://www.vworld.kr">vworld.kr</a> '
            '에서 발급받을 수 있습니다.</p>'
            f'<p style="color:{muted};">변경 사항은 자동으로 저장됩니다.</p>'
            '</body></html>'
        )
        self.troubleshootHint.setText(
            f'<span style="color:{muted};">기능이 작동하지 않을 때 '
            '로그 파일을 저장해 개발자에게 전달해 주세요.</span>'
        )

    def _setup_navigation(self):
        """
            좌측 사이드바 항목 채우기 + 페이지 전환 연결
        """
        self.navList.clear()
        for text_key, icon_path in _NAV_ITEMS:
            item = QListWidgetItem(UI_TEXTS.get(text_key, text_key))
            icon = QIcon(icon_path)
            if not icon.isNull():
                item.setIcon(icon)
            self.navList.addItem(item)

        self.navList.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.navList.setCurrentRow(0)
        self.stack.setCurrentIndex(0)

    def _load_settings(self):
        """
            현재 설정 로드
        """
        # API 키 - 사용자가 옵션 창에 직접 저장한 값만 표시 (config.py 키는 노출 X).
        # 그래야 비우고 저장한 결과가 다음에 열었을 때도 그대로 유지되어 보임.
        self.APIKey.setText(self.config.user_api_key)
        self.togglePwBtn.setChecked(False)
        self._apply_api_key_echo()

        # 프로토콜
        protocol_name = self.config.get('protocol', 'HTTPS(기본값)')
        if protocol_name == 'HTTP':
            self.HTTP.setChecked(True)
        elif protocol_name == 'HTTPS(보안무시)':
            self.HTTPSX.setChecked(True)
        else:
            self.HTTPS.setChecked(True)
        self.protocolWarnLabel.setVisible(protocol_name == 'HTTPS(보안무시)')

        # 라벨 스타일
        if self.config.land_label_style:
            self.landLabelSytleON.setChecked(True)
        else:
            self.landLabelSytleOFF.setChecked(True)

        # 헤더 표시 모드
        if self.config.header_style == HEADER_STYLE_COMPACT:
            self.headerStyleCompact.setChecked(True)
        else:
            self.headerStyleStandard.setChecked(True)

        # 툴바 표시 모드
        current_mode = self.config.toolbar_display_mode
        for radio_name, mode_key in _TB_RADIO_KEYS.items():
            radio = getattr(self, radio_name, None)
            if radio is not None:
                radio.setChecked(mode_key == current_mode)

        # 성공 안내 팝업 표시 여부
        if hasattr(self, 'showSuccessPopupCheck'):
            self.showSuccessPopupCheck.setChecked(self.config.show_success_popup)

    def _connect_signals(self):
        """
            시그널 연결
        """
        # API 키
        self.APIKey.editingFinished.connect(self._save_api_key)
        self.togglePwBtn.toggled.connect(lambda _checked=False: self._apply_api_key_echo())
        self.openVworldBtn.clicked.connect(self._open_vworld_site)

        # 프로토콜
        self.HTTP.clicked.connect(lambda: self._save_protocol('HTTP'))
        self.HTTPS.clicked.connect(lambda: self._save_protocol('HTTPS(기본값)'))
        self.HTTPSX.clicked.connect(lambda: self._save_protocol('HTTPS(보안무시)'))

        # 라벨 스타일
        self.landLabelSytleON.clicked.connect(lambda: self._save_label_style(True))
        self.landLabelSytleOFF.clicked.connect(lambda: self._save_label_style(False))

        # 헤더 표시 모드
        self.headerStyleStandard.clicked.connect(
            lambda: self._save_header_style(HEADER_STYLE_STANDARD)
        )
        self.headerStyleCompact.clicked.connect(
            lambda: self._save_header_style(HEADER_STYLE_COMPACT)
        )

        # 툴바 표시 모드
        for radio_name, mode_key in _TB_RADIO_KEYS.items():
            radio = getattr(self, radio_name, None)
            if radio is not None:
                radio.clicked.connect(
                    lambda _checked=False, m=mode_key: self._save_toolbar_mode(m)
                )

        # 성공 안내 팝업 표시 여부
        if hasattr(self, 'showSuccessPopupCheck'):
            self.showSuccessPopupCheck.toggled.connect(self._save_show_success_popup)

        # 로그 파일 저장 (문제 해결)
        self.saveLogBtn.clicked.connect(self._save_log_file)

        # 닫기 버튼 - 닫기 직전에 API 키 변경분을 한 번 더 보장 저장
        self.closeBtn.clicked.connect(self._on_close_clicked)

    def _apply_api_key_echo(self):
        """
            API 키 필드 echo 모드 결정.
            - togglePwBtn 체크(수동 오버라이드) 또는 필드 포커스 보유 시 평문 표시.
            - 그 외에는 Password 마스킹.
            버튼 라벨은 오버라이드 상태만 반영(포커스 자동 표시는 무관).
        """
        override_show = self.togglePwBtn.isChecked()
        has_focus = self.APIKey.hasFocus()
        show = override_show or has_focus
        self.APIKey.setEchoMode(
            QLineEdit.EchoMode.Normal if show else QLineEdit.EchoMode.Password
        )
        self.togglePwBtn.setText('숨김' if override_show else '표시')

    def eventFilter(self, obj, event):
        """
            APIKey 포커스 이벤트를 가로채 echo 모드 자동 토글.
        """
        if obj is self.APIKey and event.type() in (
            QEvent.Type.FocusIn, QEvent.Type.FocusOut,
        ):
            self._apply_api_key_echo()
        return super().eventFilter(obj, event)

    def _open_vworld_site(self):
        """
            V-World 사이트 열기
        """
        QDesktopServices.openUrl(QUrl("https://www.vworld.kr/dev/v4api.do"))

    @with_error_handling("API 키 저장 중 오류가 발생했습니다")
    def _save_api_key(self):
        """
            API 키 저장. 빈 값도 정상 저장으로 간주(키 제거).
        """
        api_key = self.APIKey.text().strip()

        # 비어 있으면 유효성 검사 없이 그대로 저장(키 제거)
        if api_key and not Validators.validate_api_key(api_key):
            self._flash_status("유효하지 않은 API 키 형식입니다.", level='warn')
            return

        self.config.api_key = api_key
        self.APIKey.setText(api_key)

        if api_key:
            self._flash_status("API 키가 저장되었습니다.")
            logger.info("API 키 저장됨")
        else:
            self._flash_status("API 키를 비웠습니다.")
            logger.info("API 키 비워짐")

    def _save_protocol(self, protocol: str):
        """
            프로토콜 저장
        """
        try:
            self.config.protocol = protocol
            self.protocolWarnLabel.setVisible(protocol == 'HTTPS(보안무시)')
            if protocol == 'HTTPS(보안무시)':
                logger.warning("SSL 검증 비활성화(HTTPS 보안무시) 선택됨")
            self._flash_status(f"호출 방식이 '{protocol}'로 변경되었습니다.")
            logger.info(f"프로토콜 변경: {protocol}")
        except Exception:
            logger.exception("프로토콜 저장 실패")
            self._flash_status("프로토콜 설정을 저장하지 못했습니다.", level='error')

    def _save_label_style(self, enabled: bool):
        """
            라벨 스타일 저장
        """
        try:
            self.config.land_label_style = enabled
            status = "활성화" if enabled else "비활성화"
            self._flash_status(f"지적도 라벨 표시가 {status}되었습니다.")
            logger.info(f"토지 라벨 스타일: {enabled}")
        except Exception:
            logger.exception("라벨 스타일 저장 실패")
            self._flash_status("지적도 라벨 설정을 저장하지 못했습니다.", level='error')

    def _save_toolbar_mode(self, mode_key: str):
        """
            툴바 표시 모드 저장 + 실시간 반영 시그널
        """
        try:
            if mode_key not in TOOLBAR_DISPLAY_MODES:
                mode_key = DEFAULT_TOOLBAR_DISPLAY_MODE

            self.config.toolbar_display_mode = mode_key
            _style, label = TOOLBAR_DISPLAY_MODES[mode_key]

            self.toolbarStyleChanged.emit(mode_key)
            self._flash_status(f"툴바 표시: {label}")
            logger.info(f"툴바 표시 모드: {mode_key}")
        except Exception:
            logger.exception("툴바 모드 저장 실패")
            self._flash_status("툴바 표시 설정을 저장하지 못했습니다.", level='error')

    def _save_header_style(self, style: str):
        """
            패널 헤더 표시 모드 저장 + 실시간 반영 시그널
        """
        try:
            self.config.header_style = style
            label = "요약" if style == HEADER_STYLE_COMPACT else "표준"
            self.headerStyleChanged.emit(style)
            self._flash_status(f"패널 헤더 표시: {label}")
            logger.info(f"헤더 표시 모드: {style}")
        except Exception:
            logger.exception("헤더 모드 저장 실패")
            self._flash_status("헤더 표시 설정을 저장하지 못했습니다.", level='error')

    def _on_close_clicked(self):
        """
            닫기 클릭 시 입력 중인 API 키 값을 마지막으로 한 번 더 동기화.
            (editingFinished가 누락되는 엣지 케이스 방지 - 특히 빈 값 저장)
            비교는 QSettings의 실제 사용자 키와 수행 (config.py 우선 getter는 사용 X).
        """
        current = self.APIKey.text().strip()
        if current != (self.config.user_api_key or ''):
            self._save_api_key()
        self.accept()

    @with_error_handling("로그 파일 저장 중 오류가 발생했습니다")
    def _save_log_file(self, checked=False):
        """
            진단 로그 파일을 사용자가 지정한 위치로 내보내기.
            비숙련 사용자가 바로 열어볼 수 있게 기본 확장자는 .txt.
        """
        desktop = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DesktopLocation
        )
        default_name = f"V-QGIS_로그_{date.today().isoformat()}.txt"
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "로그 파일 저장",
            f"{desktop}/{default_name}",
            "텍스트 파일 (*.txt);;모든 파일 (*)",
        )
        if not path:
            return

        if export_logs(path):
            self._flash_status("로그 파일이 저장되었습니다.")
            logger.info(f"로그 파일 내보내기: {path}")
        else:
            self._flash_status("저장할 로그가 아직 없습니다.", level='warn')

    def _save_show_success_popup(self, enabled: bool):
        """
            성공 안내 팝업 표시 여부 저장
        """
        try:
            self.config.show_success_popup = enabled
            status = "팝업으로 표시" if enabled else "표시하지 않음(조용히 처리)"
            self._flash_status(f"작업 완료 알림: {status}.")
            logger.info(f"성공 팝업 표시: {enabled}")
        except Exception:
            logger.exception("성공 팝업 설정 저장 실패")
            self._flash_status("알림 설정을 저장하지 못했습니다.", level='error')

    def _flash_status(self, message: str, level: str = 'info'):
        """
            하단 status 라벨에 짧은 피드백 표시 (자동 페이드).
            라이트/다크 테마에 맞춰 색상 자동 선택.
        """
        self.statusLabel.setStyleSheet(f"color: {_status_color(level)};")
        self.statusLabel.setText(message)
        # 오류는 사용자가 읽을 시간을 확보하도록 자동으로 사라지지 않게 한다.
        if level == 'error':
            self._status_timer.stop()
        else:
            self._status_timer.start(_STATUS_FADE_MS)

    def _clear_status(self):
        """
            status 라벨 비우기
        """
        self.statusLabel.clear()
