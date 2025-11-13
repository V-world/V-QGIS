import os
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, QVariant
from qgis.PyQt.QtWidgets import QListWidgetItem, QMenu, QDialog, QVBoxLayout, QLineEdit
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry,
    QgsPointXY, QgsCoordinateTransform, QgsCoordinateReferenceSystem,
    QgsField, QgsMultiPolygon, QgsPolygon, QgsLineString, QgsPoint
)
from typing import List, Tuple, Dict, Any
import logging

from .base_widget import BaseWidget
from ..constants import (
    UI_DIR, SEARCHES_FILE, SEARCH_RESULT_LAYER, MAX_RECENT_SEARCHES,
    DATA_ROLE_X, DATA_ROLE_Y, DATA_ROLE_TYPE, DATA_ROLE_CRS,
    WORKER_QUIT_TIMEOUT, WORKER_TERMINATE_TIMEOUT
)
from ..utils import FileManager, ApiClient, with_error_handling, with_loading_cursor
from ..core import LayerManager, SearchWorker
from ..exceptions import ApiError

logger = logging.getLogger(__name__)

FORM_CLASS, _ = uic.loadUiType(os.path.join(UI_DIR, 'v_world_dockSearch_base.ui'))


class SearchWidget(BaseWidget, FORM_CLASS):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.api_client = ApiClient()
        self.search_worker = None
        self._connect_signals()
        self._refresh_recent_searches()

    def _connect_signals(self):
        """
            시그널 연결
        """
        self.listSearch.itemDoubleClicked.connect(self._on_search_item_clicked)
        self.recentSearchs.itemDoubleClicked.connect(self._on_recent_item_clicked)
        self.inputSearch.editingFinished.connect(self._on_search_input_finished)

        # 컨텍스트 메뉴
        self.listSearch.setContextMenuPolicy(Qt.CustomContextMenu)
        self.listSearch.customContextMenuRequested.connect(self._show_search_context_menu)

        self.recentSearchs.setContextMenuPolicy(Qt.CustomContextMenu)
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

        # 기존 검색 워커 정리 (안전한 종료)
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.quit()  # 정상 종료 요청
            if not self.search_worker.wait(WORKER_QUIT_TIMEOUT):
                logger.warning("SearchWorker 정상 종료 실패, 강제 종료")
                self.search_worker.terminate()
                self.search_worker.wait(WORKER_TERMINATE_TIMEOUT)

        # 새 검색 워커 시작
        self.search_worker = SearchWorker(query, self.get_current_crs())
        self.search_worker.finished.connect(self._display_search_results)
        self.search_worker.error.connect(lambda msg: self.show_error_message("검색 오류", msg))
        self.search_worker.start()

    def _display_search_results(self, results: List[Dict[str, Any]]):
        """
            검색 결과 표시
        """
        self.listSearch.clear()

        if not results:
            self.listSearch.addItem("검색 결과 없음")
            return

        for result in results:
            item = QListWidgetItem(result['address'])
            item.setData(DATA_ROLE_X, result['x'])
            item.setData(DATA_ROLE_Y, result['y'])
            item.setData(DATA_ROLE_TYPE, result.get('type', 'unknown'))
            self.listSearch.addItem(item)

    def _on_search_item_clicked(self, item: QListWidgetItem):
        """
            검색 결과 아이템 클릭
        """
        if item.text() == "검색 결과 없음":
            return

        x = float(item.data(DATA_ROLE_X))
        y = float(item.data(DATA_ROLE_Y))
        address = item.text()

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
        try:
            x = float(item.data(DATA_ROLE_X))
            y = float(item.data(DATA_ROLE_Y))
            epsg = item.data(DATA_ROLE_CRS)
            address = item.text()

            # 좌표계 변환 필요 시
            current_crs = self.get_current_crs()
            if current_crs != epsg:
                source_crs = QgsCoordinateReferenceSystem(epsg)
                dest_crs = QgsCoordinateReferenceSystem(current_crs)

                # 좌표계 유효성 확인
                if not source_crs.isValid():
                    logger.error(f"잘못된 원본 좌표계: {epsg}")
                    self.show_error_message("좌표계 오류", f"원본 좌표계가 유효하지 않습니다: {epsg}")
                    return

                if not dest_crs.isValid():
                    logger.error(f"잘못된 대상 좌표계: {current_crs}")
                    self.show_error_message("좌표계 오류", f"대상 좌표계가 유효하지 않습니다: {current_crs}")
                    return

                transform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())

                try:
                    point = transform.transform(QgsPointXY(x, y))
                    x, y = point.x(), point.y()
                except Exception as e:
                    logger.error(f"좌표 변환 실패 ({epsg} -> {current_crs}): {e}")
                    self.show_error_message("좌표 변환 오류", f"좌표 변환에 실패했습니다: {str(e)}")
                    return

            # 지도 이동 및 마커 추가
            self.zoom_to_point(x, y)
            self._add_search_marker(x, y, address)

        except ValueError as e:
            logger.error(f"좌표 파싱 오류: {e}")
            self.show_error_message("데이터 오류", "저장된 좌표 정보가 올바르지 않습니다.")
        except Exception as e:
            logger.error(f"최근 검색 처리 오류: {e}")
            self.show_error_message("오류", f"검색 결과를 표시하는 중 오류가 발생했습니다: {str(e)}")

    def _add_to_recent_searches(self, address: str, x: float, y: float):
        """
            최근 검색에 추가
        """
        searches = FileManager.read_json(SEARCHES_FILE, {})

        # 새 검색을 맨 앞에 추가
        searches = {address: [x, y, self.get_current_crs()], **searches}

        # 최대 개수 제한
        if len(searches) > MAX_RECENT_SEARCHES:
            # 가장 오래된 항목 제거
            oldest_key = list(searches.keys())[-1]
            del searches[oldest_key]

        FileManager.write_json(SEARCHES_FILE, searches)

    def _refresh_recent_searches(self):
        """
            최근 검색 목록 새로고침
        """
        self.recentSearchs.clear()
        searches = FileManager.read_json(SEARCHES_FILE, {})

        for address, (x, y, crs) in searches.items():
            item = QListWidgetItem(address)
            item.setData(DATA_ROLE_X, x)
            item.setData(DATA_ROLE_Y, y)
            item.setData(DATA_ROLE_CRS, crs)
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
            logger.error(f"검색 마커 추가 실패: {e}")

    def _show_search_context_menu(self, position):
        """
            검색 결과 컨텍스트 메뉴
        """
        item = self.listSearch.itemAt(position)
        if not item or item.text() == "검색 결과 없음":
            return

        menu = QMenu()
        copy_action = menu.addAction("주소 복사하기")
        copy_action.triggered.connect(lambda: self._show_address_dialog(item.text()))

        menu.exec_(self.listSearch.viewport().mapToGlobal(position))

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

        menu.exec_(self.recentSearchs.viewport().mapToGlobal(position))

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
        dialog.exec_()