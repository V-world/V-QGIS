from qgis.PyQt.QtCore import Qt, QVariant
from qgis.PyQt.QtWidgets import (
    QListWidgetItem, QMenu, QDialog, QVBoxLayout, QLineEdit,
    QWidget, QTabWidget, QListWidget, QLabel, QPushButton, QHBoxLayout
)
from qgis.core import (
    QgsProject, QgsPointXY, QgsCoordinateTransform,
    QgsCoordinateReferenceSystem, QgsField,
)
from typing import List, Dict, Any

from .base_widget import BaseWidget
from ..constants import SEARCHES_FILE, SEARCH_RESULT_LAYER, MAX_RECENT_SEARCHES
from ..utils import (
    FileManager, ApiClient, with_error_handling, with_loading_cursor,
    ThemeColors, log_info, log_error,
)
from ..core import LayerManager, SearchWorker


class SearchWidget(BaseWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.api_client = ApiClient()
        self.search_worker = None
        self._stale_search_workers = []  # 취소했지만 아직 도는 워커 참조 (GC로 스레드가 죽는 것 방지)
        self._connect_signals()
        self._refresh_recent_searches()

    def _setup_ui(self):
        """코드로 UI 구성 (이전 v_world_dockSearch_base.ui 대체)"""
        self.setWindowTitle("브이월드 주소 검색")

        contents = QWidget()
        contents.setObjectName("dockWidgetContents")
        outer = QVBoxLayout(contents)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(
            self.make_brand_header(
                "브이월드 주소 검색", "주소를 검색해 지도로 이동", ":/icon_search"
            )
        )

        self.tabWidget = QTabWidget()

        # 주소 검색 탭
        tab_search = QWidget()
        search_layout = QVBoxLayout(tab_search)
        input_row = QHBoxLayout()
        input_row.setSpacing(6)
        self.inputSearch = QLineEdit()
        self.inputSearch.setPlaceholderText("도로명·지번 주소를 입력하고 Enter")
        self.inputSearch.setClearButtonEnabled(True)
        self.inputSearch.setAccessibleName("주소 검색 입력")
        input_row.addWidget(self.inputSearch)
        self.searchBtn = QPushButton("검색")
        self.searchBtn.setMinimumWidth(64)
        input_row.addWidget(self.searchBtn)
        search_layout.addLayout(input_row)

        # 사용법 힌트 (처음 사용하는 사용자를 위한 안내)
        hint = QLabel("결과를 더블클릭하거나, 선택 후 '지도에 추가'를 누르세요.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {ThemeColors.muted()};")
        search_layout.addWidget(hint)

        self.listSearch = QListWidget()
        search_layout.addWidget(self.listSearch)

        # 주요 동작 버튼 (결과 선택 시 활성화)
        self.addToMapBtn = QPushButton("지도에 추가")
        self.addToMapBtn.setEnabled(False)
        search_layout.addWidget(self.addToMapBtn)

        self.tabWidget.addTab(tab_search, "주소 검색")

        # 최근 검색 탭
        tab_recent = QWidget()
        recent_layout = QVBoxLayout(tab_recent)
        self.recentSearchs = QListWidget()
        recent_layout.addWidget(self.recentSearchs)
        self.tabWidget.addTab(tab_recent, "최근 검색")

        outer.addWidget(self.tabWidget)
        self.setWidget(contents)

        # 빈 상태 초기 안내
        self._set_list_placeholder(
            self.listSearch, "검색 결과가 여기에 표시됩니다."
        )

    def _connect_signals(self):
        """
            시그널 연결
        """
        # itemActivated: 더블클릭 + Enter 키 모두 처리(키보드 지원).
        self.listSearch.itemActivated.connect(self._on_search_item_clicked)
        self.recentSearchs.itemActivated.connect(self._on_recent_item_clicked)
        self.inputSearch.returnPressed.connect(self._on_search_input_finished)
        self.searchBtn.clicked.connect(lambda _checked=False: self._on_search_input_finished())
        self.addToMapBtn.clicked.connect(self._on_add_to_map_clicked)
        self.listSearch.itemSelectionChanged.connect(self._update_add_button_state)

        # 단축키: Ctrl+F로 검색창 포커스
        self.add_shortcut("Ctrl+F", self.inputSearch.setFocus)

        # 컨텍스트 메뉴
        self.listSearch.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.listSearch.customContextMenuRequested.connect(self._show_search_context_menu)

        self.recentSearchs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.recentSearchs.customContextMenuRequested.connect(self._show_recent_context_menu)

    @with_error_handling("검색 중 오류가 발생했습니다")
    @with_loading_cursor
    def _on_search_input_finished(self):
        """
            검색 입력 완료 시 처리
        """
        query = self.inputSearch.text().strip()
        if not query:
            return

        # 캔버스 메시지 바 대신 결과 패널 안에 진행 상태를 표시(비방해).
        self._set_list_placeholder(self.listSearch, "주소를 검색하는 중입니다…")

        # 기존 검색 워커 정리 - terminate()는 요청 중 강제 종료로 QGIS가 죽을 수 있어
        # 협조적 취소만 사용하고, 도는 워커는 stale 목록에 보관해 자연 종료를 기다린다.
        if self.search_worker and self.search_worker.isRunning():
            old = self.search_worker
            try:
                old.finished.disconnect(self._display_search_results)
                old.error.disconnect(self._on_search_error)
            except TypeError:
                pass  # 이미 끊겼으면 무시
            old.cancel()
            self._stale_search_workers.append(old)
        # 끝난 구형 워커 참조 정리
        self._stale_search_workers = [
            w for w in self._stale_search_workers if w.isRunning()
        ]

        # 새 검색 워커 시작
        self.search_worker = SearchWorker(query, self.get_current_crs())
        self.search_worker.finished.connect(self._display_search_results)
        self.search_worker.error.connect(self._on_search_error)
        self.search_worker.start()

    def _on_search_error(self, msg: str):
        """
            검색 워커 오류 처리 (워커가 이미 상세 로그를 남김)
        """
        # 이전 검색의 늦은 오류는 무시 (disconnect 전에 이벤트 큐에 들어온 경우 대비)
        if self.sender() is not None and self.sender() is not self.search_worker:
            return
        self._set_list_placeholder(
            self.listSearch, "검색 중 오류가 발생했습니다. 다시 시도해 주세요."
        )
        self.show_error_message("검색 오류", msg)

    def closeEvent(self, event):
        # 닫을 때 진행 중 워커를 협조적으로 취소하고 종료를 기다린다 (terminate 금지).
        for worker in [self.search_worker] + self._stale_search_workers:
            try:
                if worker is not None and worker.isRunning():
                    worker.cancel()
                    worker.quit()
                    worker.wait(2000)
            except Exception:
                pass
        self._stale_search_workers = []
        super().closeEvent(event)

    def _display_search_results(self, results: List[Dict[str, Any]]):
        """
            검색 결과 표시
        """
        # 이전 검색의 늦은 결과는 무시 (disconnect 전에 이벤트 큐에 들어온 경우 대비)
        if self.sender() is not None and self.sender() is not self.search_worker:
            return
        self.listSearch.clear()
        log_info(f"검색 결과 표시: {len(results)}건")

        if not results:
            self._set_list_placeholder(
                self.listSearch, "검색 결과가 없습니다. 다른 주소로 시도해 보세요."
            )
            return

        type_labels = {'road': '도로명', 'parcel': '지번'}
        for result in results:
            label = type_labels.get(result.get('type'))
            text = f"{result['address']}  ·  {label}" if label else result['address']
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, result['x'])
            item.setData(Qt.ItemDataRole.UserRole + 1, result['y'])
            item.setData(Qt.ItemDataRole.UserRole + 2, result.get('type', 'unknown'))
            # 유형 배지를 뺀 순수 주소 (최근 검색·마커·복사에 사용)
            item.setData(Qt.ItemDataRole.UserRole + 3, result['address'])
            self.listSearch.addItem(item)

    def _update_add_button_state(self):
        """
            결과 목록 선택 상태에 따라 '지도에 추가' 버튼 활성/비활성.
        """
        item = self.listSearch.currentItem()
        selectable = bool(item) and bool(item.flags() & Qt.ItemFlag.ItemIsSelectable)
        self.addToMapBtn.setEnabled(selectable)

    def _on_add_to_map_clicked(self, checked=False):
        """
            '지도에 추가' 버튼 - 현재 선택된 결과를 지도에 추가.
        """
        item = self.listSearch.currentItem()
        if item is not None:
            self._on_search_item_clicked(item)

    def _on_search_item_clicked(self, item: QListWidgetItem):
        """
            검색 결과 아이템 클릭
        """
        # 빈 상태(안내) 항목은 무시
        if not (item.flags() & Qt.ItemFlag.ItemIsSelectable):
            return

        x = float(item.data(Qt.ItemDataRole.UserRole))
        y = float(item.data(Qt.ItemDataRole.UserRole + 1))
        # 유형 배지를 뺀 순수 주소 (없으면 표시 텍스트로 폴백)
        address = item.data(Qt.ItemDataRole.UserRole + 3) or item.text()

        # 최근 검색에 추가
        self._add_to_recent_searches(address, x, y)

        # 지도 이동 및 마커 추가
        self.zoom_to_point(x, y)
        self._add_search_marker(x, y, address)

        # 최근 검색 목록 새로고침
        self._refresh_recent_searches()

    def _on_recent_item_clicked(self, item: QListWidgetItem):
        """
            최근 검색 아이템 클릭
        """
        # 빈 상태(안내) 항목은 무시
        if not (item.flags() & Qt.ItemFlag.ItemIsSelectable):
            return

        x = float(item.data(Qt.ItemDataRole.UserRole))
        y = float(item.data(Qt.ItemDataRole.UserRole + 1))
        epsg = item.data(Qt.ItemDataRole.UserRole + 2)
        address = item.text()

        # 좌표계 변환 필요 시
        current_crs = self.get_current_crs()
        if current_crs != epsg:
            source_crs = QgsCoordinateReferenceSystem(epsg)
            dest_crs = QgsCoordinateReferenceSystem(current_crs)
            transform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())

            point = transform.transform(QgsPointXY(x, y))
            x, y = point.x(), point.y()

        # 지도 이동 및 마커 추가
        self.zoom_to_point(x, y)
        self._add_search_marker(x, y, address)

    def _add_to_recent_searches(self, address: str, x: float, y: float):
        """
            최근 검색에 추가
        """
        searches = FileManager.read_json(SEARCHES_FILE, {})

        # 같은 주소가 이미 있으면 제거 후 최신 좌표로 맨 앞에 다시 삽입
        searches.pop(address, None)
        searches = {address: [x, y, self.get_current_crs()], **searches}

        # 최대 개수 제한 (가장 오래된 항목부터 제거)
        while len(searches) > MAX_RECENT_SEARCHES:
            oldest_key = list(searches.keys())[-1]
            del searches[oldest_key]

        FileManager.write_json(SEARCHES_FILE, searches)

    def _refresh_recent_searches(self):
        """
            최근 검색 목록 새로고침
        """
        self.recentSearchs.clear()
        searches = FileManager.read_json(SEARCHES_FILE, {})

        if not searches:
            self._set_list_placeholder(
                self.recentSearchs, "최근 검색 기록이 없습니다."
            )
            return

        for address, (x, y, crs) in searches.items():
            item = QListWidgetItem(address)
            item.setData(Qt.ItemDataRole.UserRole, x)
            item.setData(Qt.ItemDataRole.UserRole + 1, y)
            item.setData(Qt.ItemDataRole.UserRole + 2, crs)
            self.recentSearchs.addItem(item)

    def _add_search_marker(self, x: float, y: float, address: str):
        """
            검색 결과 마커 추가
        """
        try:
            # 레이어 가져오기 또는 생성
            layer = LayerManager.get_or_create_layer(
                SEARCH_RESULT_LAYER,
                "Point",
                self.get_current_crs(),
                [QgsField("addr", QVariant.String)]
            )

            # 포인트 추가
            LayerManager.add_point_to_layer(
                layer,
                QgsPointXY(x, y),
                [address]
            )

            self.canvas.refresh()

        except Exception as e:
            log_error(f"검색 마커 추가 실패: {type(e).__name__}: {e}")

    def _show_search_context_menu(self, position):
        """
            검색 결과 컨텍스트 메뉴
        """
        item = self.listSearch.itemAt(position)
        if not item or not (item.flags() & Qt.ItemFlag.ItemIsSelectable):
            return

        address = item.data(Qt.ItemDataRole.UserRole + 3) or item.text()
        menu = QMenu()
        copy_action = menu.addAction("주소 복사하기")
        copy_action.triggered.connect(lambda: self._show_address_dialog(address))

        menu.exec(self.listSearch.viewport().mapToGlobal(position))

    def _show_recent_context_menu(self, position):
        """
            최근 검색 컨텍스트 메뉴
        """
        item = self.recentSearchs.itemAt(position)
        if not item:
            return

        menu = QMenu()
        copy_action = menu.addAction("주소 복사하기")
        copy_action.triggered.connect(lambda: self._show_address_dialog(item.text()))

        menu.exec(self.recentSearchs.viewport().mapToGlobal(position))

    def _show_address_dialog(self, address: str):
        """
            주소 복사 대화상자
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("주소 복사하기")
        dialog.setModal(True)

        layout = QVBoxLayout()
        line_edit = QLineEdit(address)
        line_edit.selectAll()
        layout.addWidget(line_edit)

        dialog.setLayout(layout)
        dialog.exec()