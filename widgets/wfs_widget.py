from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtWidgets import (
    QListWidgetItem, QMenu, QWidget, QGridLayout, QLabel, QLineEdit,
    QTabWidget, QListWidget, QAbstractItemView, QVBoxLayout, QPushButton,
)
from qgis.PyQt.QtGui import QDesktopServices
import logging

from .base_widget import BaseWidget
from ..constants import FAVORITES_FILE
from ..utils import FileManager, ApiClient, with_error_handling, with_loading_cursor, require_api_key, ThemeColors
from ..core import LayerManager
from ..exceptions import ApiError, SSLError, AuthenticationError

logger = logging.getLogger(__name__)


class WfsWidget(BaseWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.api_client = ApiClient()
        self._apply_theme_text()
        self._connect_signals()
        self._load_wfs_layers()
        self._refresh_favorites()

    def _build_ui(self):
        """코드로 UI 구성 (이전 v_world_dockWfs_base.ui 대체)."""
        self.setWindowTitle("브이월드 주제도")

        contents = QWidget()
        contents.setObjectName("dockWidgetContents")
        outer = QVBoxLayout(contents)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(
            self.make_brand_header(
                "브이월드 주제도", "국가 공간정보 주제도 불러오기", ":/icon_layer"
            )
        )

        body = QWidget()
        grid = QGridLayout(body)
        outer.addWidget(body)

        # 안내 링크 라벨 (텍스트는 _apply_theme_text에서 채움)
        self.linktoVworld = QLabel()
        self.linktoVworld.setTextFormat(Qt.TextFormat.AutoText)
        self.linktoVworld.setAlignment(
            Qt.AlignmentFlag.AlignJustify | Qt.AlignmentFlag.AlignVCenter
        )
        self.linktoVworld.setWordWrap(True)
        grid.addWidget(self.linktoVworld, 0, 0)

        # 검색
        self.wfsSearch = QLineEdit()
        self.wfsSearch.setPlaceholderText("주제도 이름으로 검색")
        self.wfsSearch.setClearButtonEnabled(True)
        self.wfsSearch.setAccessibleName("주제도 검색 입력")
        grid.addWidget(self.wfsSearch, 1, 0)

        # 사용법 힌트
        self.wfsHint = QLabel("항목을 더블클릭하면 지도에 불러옵니다. 우클릭하면 즐겨찾기·다운로드를 이용할 수 있습니다.")
        self.wfsHint.setWordWrap(True)
        self.wfsHint.setStyleSheet(f"color: {ThemeColors.muted()};")
        grid.addWidget(self.wfsHint, 2, 0)

        # 탭 (주제도 목록 / 즐겨찾기)
        self.tabWidget = QTabWidget()

        tab_list = QWidget()
        tab_list_layout = QGridLayout(tab_list)
        self.wfsList = QListWidget()
        self.wfsList.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        tab_list_layout.addWidget(self.wfsList, 0, 0)

        # 빈 상태/오류 시 재시도 버튼 (성공적으로 목록을 받으면 숨김)
        self.wfsReloadBtn = QPushButton("주제도 목록 다시 불러오기")
        self.wfsReloadBtn.setVisible(False)
        tab_list_layout.addWidget(self.wfsReloadBtn, 1, 0)

        self.tabWidget.addTab(tab_list, "주제도 목록")

        tab_fav = QWidget()
        tab_fav_layout = QGridLayout(tab_fav)
        self.wfsFavorites = QListWidget()
        self.wfsFavorites.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        tab_fav_layout.addWidget(self.wfsFavorites, 0, 0)
        self.tabWidget.addTab(tab_fav, "즐겨찾기")

        grid.addWidget(self.tabWidget, 3, 0)

        # 주요 동작 버튼 (선택 시 활성화)
        self.wfsAddBtn = QPushButton("지도에 추가")
        self.wfsAddBtn.setEnabled(False)
        grid.addWidget(self.wfsAddBtn, 4, 0)

        self.setWidget(contents)

        # 빈 상태 초기 안내 (로드/즐겨찾기 새로고침에서 갱신)
        self._set_list_placeholder(
            self.wfsList,
            "주제도 목록이 비어 있습니다. API 키를 설정한 뒤 "
            "'주제도 목록 다시 불러오기'를 눌러 주세요."
        )
        self.wfsReloadBtn.setVisible(True)
        self._set_list_placeholder(
            self.wfsFavorites, "즐겨찾기가 없습니다. 목록에서 우클릭하여 추가하세요."
        )

    def _apply_theme_text(self):
        """
            안내 라벨(linktoVworld) 색상을 라이트/다크 테마에 맞춰 재적용.
        """
        if not hasattr(self, 'linktoVworld'):
            return
        link = ThemeColors.link()
        muted = ThemeColors.muted()
        # 캐비엇을 앞세우지 않고 '미리보기 → 전체는 다운로드' 흐름으로 간결하게.
        self.linktoVworld.setText(
            '<html><body><p>'
            '주제도는 미리보기용입니다. 전체 데이터는 '
            '<a href="https://www.vworld.kr/dtmk/dtmk_ntads_s001.do">'
            f'<span style="font-weight:600; text-decoration:underline; color:{link};">'
            '브이월드에서 다운로드</span></a> 하세요. '
            f'<span style="color:{muted};">(축척 1:1,000 권장)</span>'
            '</p></body></html>'
        )

    def _connect_signals(self):
        """
            시그널 연결
        """
        # itemActivated: 더블클릭 + Enter 키 모두 처리(키보드 지원).
        self.wfsList.itemActivated.connect(self._on_wfs_item_clicked)
        self.wfsFavorites.itemActivated.connect(self._on_favorite_item_clicked)
        self.wfsSearch.textChanged.connect(self._on_search_text_changed)
        self.wfsAddBtn.clicked.connect(self._on_add_selected_clicked)
        # clicked의 checked 인자가 데코레이터(*args)로 흘러들지 않도록 무인자 람다 사용
        self.wfsReloadBtn.clicked.connect(lambda: self._load_wfs_layers())
        self.wfsList.itemSelectionChanged.connect(self._update_add_state)
        self.wfsFavorites.itemSelectionChanged.connect(self._update_add_state)
        self.tabWidget.currentChanged.connect(self._update_add_state)

        # 단축키: Ctrl+F로 검색창 포커스
        self.add_shortcut("Ctrl+F", self.wfsSearch.setFocus)

        # 컨텍스트 메뉴
        self.wfsList.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.wfsList.customContextMenuRequested.connect(self._show_wfs_context_menu)

        self.wfsFavorites.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.wfsFavorites.customContextMenuRequested.connect(self._show_favorites_context_menu)

        # V-World 링크
        self.linktoVworld.linkActivated.connect(self._open_vworld_website)

    @with_error_handling("WFS 레이어 목록을 가져오는 중 오류가 발생했습니다")
    @with_loading_cursor
    @require_api_key
    def _load_wfs_layers(self):
        """
            WFS 레이어 목록 로드
        """
        try:
            # Capabilities 가져오기
            root = self.api_client.get_wfs_capabilities()

            # 레이어 목록 파싱
            self.wfsList.clear()
            for feature_type in root.findall(".//FeatureType"):
                name_elem = feature_type.find("Name")
                title_elem = feature_type.find("Title")

                if name_elem is not None and title_elem is not None:
                    item = QListWidgetItem(f"{title_elem.text}[{name_elem.text}]")
                    item.setData(Qt.ItemDataRole.UserRole, name_elem.text)
                    self.wfsList.addItem(item)

            if self.wfsList.count() == 0:
                self._set_list_placeholder(
                    self.wfsList, "표시할 주제도가 없습니다."
                )
                self.wfsReloadBtn.setVisible(True)
            else:
                self.wfsList.sortItems()
                self.wfsReloadBtn.setVisible(False)
            logger.info(f"WFS 레이어 {self.wfsList.count()}개 로드 완료")

        # 원인별 안내 - 하위 예외(인증/SSL)를 먼저 잡아야 한다 (ApiError의 하위 클래스)
        except AuthenticationError as e:
            self._show_load_failure(
                "API 키가 없거나 올바르지 않습니다. "
                "설정 ▸ API 키에서 브이월드 인증키를 확인해 주세요.", e
            )
        except SSLError as e:
            self._show_load_failure(
                "보안(SSL) 인증 오류입니다. 사내망/보안장비 환경이라면 "
                "설정 ▸ 네트워크에서 'HTTPS (보안 무시)'를 선택한 뒤 다시 시도해 주세요.", e
            )
        except ApiError as e:
            self._show_load_failure(
                "서버에 연결하지 못했습니다. 네트워크 연결을 확인한 뒤 "
                "'주제도 목록 다시 불러오기'를 눌러 주세요.", e
            )

    def _show_load_failure(self, message: str, error: Exception):
        """
            주제도 목록 로드 실패 공통 처리 - 안내 placeholder + 재시도 버튼 + 오류 알림.
        """
        logger.error(f"WFS 레이어 로드 실패: {error}")
        self._set_list_placeholder(self.wfsList, message)
        self.wfsReloadBtn.setVisible(True)
        self.show_error_message("주제도 불러오기 실패", message)

    def _on_search_text_changed(self, text: str):
        """
            검색 텍스트 변경
        """
        search_text = text.lower()

        # WFS 목록 필터링
        for i in range(self.wfsList.count()):
            item = self.wfsList.item(i)
            item.setHidden(search_text not in item.text().lower())

        # 즐겨찾기 목록 필터링
        for i in range(self.wfsFavorites.count()):
            item = self.wfsFavorites.item(i)
            item.setHidden(search_text not in item.text().lower())

    @with_error_handling("레이어 추가 중 오류가 발생했습니다")
    @with_loading_cursor
    def _on_wfs_item_clicked(self, item: QListWidgetItem):
        """
            WFS 아이템 더블클릭
        """
        # 빈 상태(안내) 항목은 무시
        if not (item.flags() & Qt.ItemFlag.ItemIsSelectable):
            return

        layer_name = item.data(Qt.ItemDataRole.UserRole)
        layer_title = item.text().split("[")[0]

        self._add_wfs_layer(layer_title, layer_name)

    def _on_favorite_item_clicked(self, item: QListWidgetItem):
        """
            즐겨찾기 아이템 더블클릭
        """
        self._on_wfs_item_clicked(item)

    def _active_list(self) -> QListWidget:
        """ 현재 탭의 리스트 위젯 (0=주제도 목록, 1=즐겨찾기). """
        return self.wfsFavorites if self.tabWidget.currentIndex() == 1 else self.wfsList

    def _selected_layer_items(self):
        """ 현재 탭에서 선택된 실제(안내가 아닌) 항목 목록. """
        return [
            it for it in self._active_list().selectedItems()
            if it.flags() & Qt.ItemFlag.ItemIsSelectable
        ]

    def _update_add_state(self, *args):
        """ 선택 상태에 따라 '지도에 추가' 버튼 활성/비활성. """
        self.wfsAddBtn.setEnabled(bool(self._selected_layer_items()))

    def _on_add_selected_clicked(self, checked=False):
        """ '지도에 추가' 버튼 - 현재 탭에서 선택한 주제도를 모두 추가. """
        for item in self._selected_layer_items():
            self._on_wfs_item_clicked(item)

    def _add_wfs_layer(self, layer_title: str, layer_name: str):
        """
            WFS 레이어 추가
        """
        try:
            LayerManager.add_wfs_layer(
                layer_title,
                layer_name,
                self.get_current_crs()
            )

            self.show_success_message(
                "주제도 추가", f"'{layer_title}' 주제도를 지도에 추가했습니다."
            )

        except Exception as e:
            logger.error(f"WFS 레이어 추가 실패: {e}")
            self.show_error_message("레이어 추가 실패", str(e))

    def _show_wfs_context_menu(self, position):
        """
            WFS 목록 컨텍스트 메뉴
        """
        item = self.wfsList.itemAt(position)
        if not item or not (item.flags() & Qt.ItemFlag.ItemIsSelectable):
            return

        menu = QMenu()

        # 즐겨찾기 추가
        add_favorite = menu.addAction("즐겨찾기 추가")
        add_favorite.triggered.connect(lambda: self._add_to_favorites(item))

        # 다운로드 링크
        download = menu.addAction("다운로드 바로가기")
        download.triggered.connect(lambda: self._open_download_page(item))

        menu.exec(self.wfsList.viewport().mapToGlobal(position))

    def _show_favorites_context_menu(self, position):
        """
            즐겨찾기 컨텍스트 메뉴
        """
        item = self.wfsFavorites.itemAt(position)
        if not item or not (item.flags() & Qt.ItemFlag.ItemIsSelectable):
            return

        menu = QMenu()

        # 즐겨찾기 제거
        remove_favorite = menu.addAction("즐겨찾기 삭제")
        remove_favorite.triggered.connect(lambda: self._remove_from_favorites(item))

        menu.exec(self.wfsFavorites.viewport().mapToGlobal(position))

    def _add_to_favorites(self, item: QListWidgetItem):
        """
            즐겨찾기 추가
        """
        favorites = FileManager.read_json(FAVORITES_FILE, {})

        layer_name = item.data(Qt.ItemDataRole.UserRole)
        layer_title = item.text().split("[")[0].strip()

        favorites[layer_name] = layer_title

        FileManager.write_json(FAVORITES_FILE, favorites)
        self._refresh_favorites()

        self.show_success_message(
            "즐겨찾기", f"'{layer_title}'을(를) 즐겨찾기에 추가했습니다."
        )

    def _remove_from_favorites(self, item: QListWidgetItem):
        """
            즐겨찾기 제거
        """
        layer_name = item.data(Qt.ItemDataRole.UserRole)
        layer_title = item.text().split("[")[0].strip()

        # 실수 삭제 방지 - 삭제 전 확인
        if not self.show_question_message(
            "즐겨찾기 삭제",
            f"'{layer_title}'을(를) 즐겨찾기에서 삭제할까요?"
        ):
            return

        favorites = FileManager.read_json(FAVORITES_FILE, {})

        if layer_name in favorites:
            del favorites[layer_name]
            FileManager.write_json(FAVORITES_FILE, favorites)
            self._refresh_favorites()

            self.show_success_message("즐겨찾기", "즐겨찾기에서 삭제했습니다.")

    def _refresh_favorites(self):
        """
            즐겨찾기 목록 새로고침
        """
        self.wfsFavorites.clear()

        favorites = FileManager.read_json(FAVORITES_FILE, {})

        if not favorites:
            self._set_list_placeholder(
                self.wfsFavorites, "즐겨찾기가 없습니다. 목록에서 우클릭하여 추가하세요."
            )
            return

        for layer_name, layer_title in favorites.items():
            item = QListWidgetItem(f"{layer_title}[{layer_name}]")
            item.setData(Qt.ItemDataRole.UserRole, layer_name)
            self.wfsFavorites.addItem(item)

    def _open_download_page(self, item: QListWidgetItem):
        """
            다운로드 페이지 열기
        """
        layer_title = item.text().split("[")[0].strip()
        url = f"https://vworld.kr/dtmk/dtmk_ntads_s001.do?searchKeyword={layer_title}&searchFrm=SHP"
        QDesktopServices.openUrl(QUrl(url))

    def _open_vworld_website(self):
        QDesktopServices.openUrl(QUrl("https://www.vworld.kr/dtmk/dtmk_ntads_s001.do"))