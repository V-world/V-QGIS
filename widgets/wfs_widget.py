import os
import xml.etree.ElementTree as ET
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtWidgets import QListWidgetItem, QMenu
from qgis.PyQt.QtGui import QDesktopServices
from typing import Dict, List
import logging

from .base_widget import BaseWidget
from ..constants import UI_DIR, FAVORITES_FILE
from ..utils import FileManager, ApiClient, with_error_handling, with_loading_cursor, require_api_key
from ..core import LayerManager
from ..exceptions import ApiError

logger = logging.getLogger(__name__)

FORM_CLASS, _ = uic.loadUiType(os.path.join(UI_DIR, 'v_world_dockWfs_base.ui'))


class WfsWidget(BaseWidget, FORM_CLASS):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.api_client = ApiClient()
        self._connect_signals()
        self._load_wfs_layers()
        self._refresh_favorites()

    def _connect_signals(self):
        """
            시그널 연결
        """
        self.wfsList.itemDoubleClicked.connect(self._on_wfs_item_clicked)
        self.wfsFavorites.itemDoubleClicked.connect(self._on_favorite_item_clicked)
        self.wfsSearch.textChanged.connect(self._on_search_text_changed)

        # 컨텍스트 메뉴
        self.wfsList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.wfsList.customContextMenuRequested.connect(self._show_wfs_context_menu)

        self.wfsFavorites.setContextMenuPolicy(Qt.CustomContextMenu)
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
            for feature_type in root.findall(".//FeatureType"):
                name_elem = feature_type.find("Name")
                title_elem = feature_type.find("Title")

                if name_elem is not None and title_elem is not None:
                    item = QListWidgetItem(f"{title_elem.text}[{name_elem.text}]")
                    item.setData(Qt.UserRole, name_elem.text)
                    self.wfsList.addItem(item)

            self.wfsList.sortItems()
            logger.info(f"WFS 레이어 {self.wfsList.count()}개 로드 완료")

        except ApiError as e:
            logger.error(f"WFS 레이어 로드 실패: {e}")
            self.show_error_message("WFS 오류", str(e))

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
        layer_name = item.data(Qt.UserRole)
        layer_title = item.text().split("[")[0]

        self._add_wfs_layer(layer_title, layer_name)

    def _on_favorite_item_clicked(self, item: QListWidgetItem):
        """
            즐겨찾기 아이템 더블클릭
        """
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

            self.show_info_message("성공", f"{layer_title} 레이어가 추가되었습니다.")

        except Exception as e:
            logger.error(f"WFS 레이어 추가 실패: {e}")
            self.show_error_message("레이어 추가 실패", str(e))

    def _show_wfs_context_menu(self, position):
        """
            WFS 목록 컨텍스트 메뉴
        """
        item = self.wfsList.itemAt(position)
        if not item:
            return

        menu = QMenu()

        # 즐겨찾기 추가
        add_favorite = menu.addAction("즐겨찾기 추가")
        add_favorite.triggered.connect(lambda: self._add_to_favorites(item))

        # 다운로드 링크
        download = menu.addAction("다운로드 바로가기")
        download.triggered.connect(lambda: self._open_download_page(item))

        menu.exec_(self.wfsList.viewport().mapToGlobal(position))

    def _show_favorites_context_menu(self, position):
        """
            즐겨찾기 컨텍스트 메뉴
        """
        item = self.wfsFavorites.itemAt(position)
        if not item:
            return

        menu = QMenu()

        # 즐겨찾기 제거
        remove_favorite = menu.addAction("즐겨찾기 삭제")
        remove_favorite.triggered.connect(lambda: self._remove_from_favorites(item))

        menu.exec_(self.wfsFavorites.viewport().mapToGlobal(position))

    def _add_to_favorites(self, item: QListWidgetItem):
        """
            즐겨찾기 추가
        """
        favorites = FileManager.read_json(FAVORITES_FILE, {})

        layer_name = item.data(Qt.UserRole)
        layer_title = item.text().split("[")[0].strip()

        favorites[layer_name] = layer_title

        FileManager.write_json(FAVORITES_FILE, favorites)
        self._refresh_favorites()

        self.show_info_message("즐겨찾기", "즐겨찾기에 추가되었습니다.")

    def _remove_from_favorites(self, item: QListWidgetItem):
        """
            즐겨찾기 제거
        """
        favorites = FileManager.read_json(FAVORITES_FILE, {})

        layer_name = item.data(Qt.UserRole)

        if layer_name in favorites:
            del favorites[layer_name]
            FileManager.write_json(FAVORITES_FILE, favorites)
            self._refresh_favorites()

            self.show_info_message("즐겨찾기", "즐겨찾기에서 제거되었습니다.")

    def _refresh_favorites(self):
        """
            즐겨찾기 목록 새로고침
        """
        self.wfsFavorites.clear()

        favorites = FileManager.read_json(FAVORITES_FILE, {})

        for layer_name, layer_title in favorites.items():
            item = QListWidgetItem(f"{layer_title}[{layer_name}]")
            item.setData(Qt.UserRole, layer_name)
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