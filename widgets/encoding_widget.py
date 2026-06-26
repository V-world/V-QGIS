import logging

from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import (
    QListWidgetItem, QListWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QToolButton, QPushButton, QGroupBox, QAbstractItemView,
)
from qgis.core import QgsProject, QgsVectorLayer

from .base_widget import BaseDialog
from ..constants import ERROR_MESSAGES
from ..core import LayerManager
from ..utils import with_error_handling, with_loading_cursor, ThemeColors

logger = logging.getLogger(__name__)

_STATUS_FADE_MS = 3000


def _status_color(level: str) -> str:
    if level == 'warn':
        return ThemeColors.status_warn()
    if level == 'error':
        return ThemeColors.status_error()
    return ThemeColors.status_info()


class EncodingWidget(BaseDialog):
    """
        벡터 레이어 인코딩 일괄 변경 다이얼로그.
        - 검색/전체 선택/선택 해제/새로고침 지원
        - 항목에 현재 인코딩 표시
        - 선택 개수 카운터 + 인라인 상태 피드백
        - 적용할 인코딩 버튼은 선택이 있을 때만 활성화
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self._clear_status)

        self._apply_theme_text()
        self._connect_signals()
        self.refresh_layer_list()

    def _build_ui(self):
        """코드로 UI 구성 (이전 v_world_dockEncode_base.ui 대체)."""
        self.setWindowTitle("인코딩 변경")
        self.setMinimumSize(480, 400)
        self.resize(540, 460)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        # 헤더 (브이월드 브랜드 스트립)
        root.addWidget(
            self.make_brand_header(
                "인코딩 변경", "벡터 레이어 속성 인코딩 일괄 변경", ":/icon_languages"
            )
        )
        self.encodingHint = QLabel()
        self.encodingHint.setWordWrap(True)
        root.addWidget(self.encodingHint)

        # 검색 행
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.layerSearch = QLineEdit()
        self.layerSearch.setPlaceholderText("레이어 이름 검색...")
        self.layerSearch.setClearButtonEnabled(True)
        search_row.addWidget(self.layerSearch)
        self.refreshBtn = QToolButton()
        self.refreshBtn.setText("새로고침")
        self.refreshBtn.setToolTip("현재 QGIS 프로젝트의 벡터 레이어를 다시 불러옵니다.")
        self.refreshBtn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        search_row.addWidget(self.refreshBtn)
        root.addLayout(search_row)

        # 선택 도구 모음
        selection_toolbar = QHBoxLayout()
        selection_toolbar.setSpacing(8)
        self.selectAllBtn = QToolButton()
        self.selectAllBtn.setText("전체 선택")
        self.selectAllBtn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        selection_toolbar.addWidget(self.selectAllBtn)
        self.clearSelectionBtn = QToolButton()
        self.clearSelectionBtn.setText("선택 해제")
        self.clearSelectionBtn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        selection_toolbar.addWidget(self.clearSelectionBtn)
        selection_toolbar.addStretch(1)
        self.selectionCount = QLabel("선택 0 / 0")
        selection_toolbar.addWidget(self.selectionCount)
        root.addLayout(selection_toolbar)

        # 레이어 목록
        self.layersList = QListWidget()
        self.layersList.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.layersList.setAlternatingRowColors(True)
        self.layersList.setUniformItemSizes(True)
        root.addWidget(self.layersList)

        # 인코딩 버튼 그룹
        self.encodingGroup = QGroupBox("적용할 인코딩")
        encoding_layout = QHBoxLayout(self.encodingGroup)
        encoding_layout.setSpacing(8)
        self.encodingUTF = QPushButton("UTF-8")
        self.encodingUTF.setToolTip("최신 표준. 한글 포함 다국어 모두 지원.")
        self.encodingUTF.setMinimumHeight(32)
        self.encodingCP = QPushButton("CP949 / MS949")
        self.encodingCP.setToolTip("Windows 한글 인코딩. (QGIS 3.17+는 자동으로 MS949 사용)")
        self.encodingCP.setMinimumHeight(32)
        self.encodingEUC = QPushButton("EUC-KR")
        self.encodingEUC.setToolTip("구형 한글 인코딩. CP949의 부분집합.")
        self.encodingEUC.setMinimumHeight(32)
        for btn in (self.encodingUTF, self.encodingCP, self.encodingEUC):
            encoding_layout.addWidget(btn)
        root.addWidget(self.encodingGroup)

        # 푸터
        footer_row = QHBoxLayout()
        footer_row.setSpacing(8)
        self.statusLabel = QLabel("")
        self.statusLabel.setWordWrap(True)
        footer_row.addWidget(self.statusLabel)
        footer_row.addStretch(1)
        self.closeBtn = QPushButton("닫기")
        self.closeBtn.setMinimumWidth(80)
        footer_row.addWidget(self.closeBtn)
        root.addLayout(footer_row)

    def _apply_theme_text(self):
        """
            라이트/다크 테마에 맞춰 헤더 부제 색상 재적용.
        """
        muted = ThemeColors.muted()
        self.encodingHint.setText(
            f'<span style="color:{muted};">한글이 깨져 보일 때 '
            f'UTF-8 ↔ CP949/EUC-KR 사이에서 전환하세요.</span>'
        )
        self.selectionCount.setStyleSheet(f"color: {muted};")

    def _connect_signals(self):
        # 인코딩 버튼
        self.encodingUTF.clicked.connect(lambda _checked=False: self._apply_encoding('UTF-8'))
        self.encodingCP.clicked.connect(lambda _checked=False: self._apply_encoding('CP949'))
        self.encodingEUC.clicked.connect(lambda _checked=False: self._apply_encoding('EUC-KR'))

        # 목록 도구
        self.refreshBtn.clicked.connect(self.refresh_layer_list)
        self.selectAllBtn.clicked.connect(self._select_all_visible)
        self.clearSelectionBtn.clicked.connect(self.layersList.clearSelection)
        self.layerSearch.textChanged.connect(self._on_search_changed)
        self.layersList.itemSelectionChanged.connect(self._on_selection_changed)

        # 닫기
        self.closeBtn.clicked.connect(self.accept)

        # 단축키: Ctrl+F로 레이어 검색창 포커스
        self.add_shortcut("Ctrl+F", self.layerSearch.setFocus)

    # ------------------------------------------------------------------
    # 목록 구성
    # ------------------------------------------------------------------
    def refresh_layer_list(self):
        """
            프로젝트의 벡터 레이어를 목록에 채움. 매 호출마다 클리어 후 재구성.
            기존에 선택돼 있던 레이어는 재선택을 시도해 연속 작업 흐름을 유지.
        """
        # 재선택을 위한 이전 선택 캡처
        prev_selected = {
            it.data(Qt.ItemDataRole.UserRole)
            for it in self.layersList.selectedItems()
            if it.data(Qt.ItemDataRole.UserRole)
        }

        self.layersList.clear()

        vector_layers = [
            lyr for lyr in QgsProject.instance().mapLayers().values()
            if isinstance(lyr, QgsVectorLayer)
        ]

        if not vector_layers:
            placeholder = QListWidgetItem("프로젝트에 벡터 레이어가 없습니다.")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.layersList.addItem(placeholder)
            self._update_selection_state()
            return

        for lyr in vector_layers:
            name = lyr.name()
            current_enc = self._safe_encoding(lyr)
            label = f"{name}    [{current_enc}]" if current_enc else name
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setToolTip(
                f"레이어: {name}\n현재 인코딩: {current_enc or '알 수 없음'}\n"
                f"소스: {lyr.source()}"
            )
            if name in prev_selected:
                item.setSelected(True)
            self.layersList.addItem(item)

        # 검색 필터가 입력되어 있으면 즉시 재적용
        self._on_search_changed(self.layerSearch.text())
        self._update_selection_state()

    @staticmethod
    def _safe_encoding(layer: QgsVectorLayer) -> str:
        """
            레이어 현재 인코딩 안전 조회. 제공자 미지원/예외 시 빈 문자열.
        """
        try:
            provider = layer.dataProvider()
            return provider.encoding() if provider else ''
        except Exception:
            return ''

    # ------------------------------------------------------------------
    # 선택/검색 인터랙션
    # ------------------------------------------------------------------
    def _on_search_changed(self, text: str):
        """
            검색어로 항목 표시/숨김. UserRole이 있는(=실제 레이어) 항목만 필터.
        """
        needle = (text or '').strip().lower()
        for i in range(self.layersList.count()):
            item = self.layersList.item(i)
            name = item.data(Qt.ItemDataRole.UserRole)
            if not name:
                continue
            item.setHidden(bool(needle) and needle not in item.text().lower())
        self._update_selection_state()

    def _select_all_visible(self):
        """
            현재 보이는(필터 통과) 레이어 항목을 모두 선택.
        """
        for i in range(self.layersList.count()):
            item = self.layersList.item(i)
            if item.data(Qt.ItemDataRole.UserRole) and not item.isHidden():
                item.setSelected(True)

    def _on_selection_changed(self):
        self._update_selection_state()

    def _update_selection_state(self):
        """
            선택 개수 라벨 갱신 + 인코딩 버튼 활성 토글.
        """
        selectable = sum(
            1 for i in range(self.layersList.count())
            if self.layersList.item(i).data(Qt.ItemDataRole.UserRole)
            and not self.layersList.item(i).isHidden()
        )
        selected = len([
            it for it in self.layersList.selectedItems()
            if it.data(Qt.ItemDataRole.UserRole)
        ])
        self.selectionCount.setText(f"선택 {selected} / {selectable}")

        has_selection = selected > 0
        for btn in (self.encodingUTF, self.encodingCP, self.encodingEUC):
            btn.setEnabled(has_selection)

    # ------------------------------------------------------------------
    # 인코딩 적용
    # ------------------------------------------------------------------
    @with_error_handling("인코딩 변경 중 오류가 발생했습니다")
    @with_loading_cursor
    def _apply_encoding(self, encoding: str):
        """
            선택된 벡터 레이어들의 인코딩 변경. 인라인 상태로 결과 알림.
        """
        items = self.layersList.selectedItems()
        names = [
            it.data(Qt.ItemDataRole.UserRole)
            for it in items
            if it.data(Qt.ItemDataRole.UserRole)
        ]

        if not names:
            self._flash_status(ERROR_MESSAGES['no_layer_selected'], level='warn')
            return

        LayerManager.change_layer_encoding(names, encoding)
        self._flash_status(
            f"{len(names)}개 레이어를 {encoding}(으)로 변경했습니다.",
            level='info',
        )
        logger.info(f"인코딩 변경: {encoding}, 레이어={names}")

        # 변경 후 현재 인코딩 표시가 옛 값으로 남지 않도록 목록 갱신
        self.refresh_layer_list()

    # ------------------------------------------------------------------
    # 인라인 상태 표시
    # ------------------------------------------------------------------
    def _flash_status(self, message: str, level: str = 'info'):
        """
            하단 status 라벨에 짧은 피드백 표시 (자동 페이드).
        """
        self.statusLabel.setStyleSheet(f"color: {_status_color(level)};")
        self.statusLabel.setText(message)
        self._status_timer.start(_STATUS_FADE_MS)

    def _clear_status(self):
        self.statusLabel.clear()
