import os
from PyQt5.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from PyQt5.QtWidgets import QAction, QMenu, QMessageBox, QFileDialog, QDialog, QVBoxLayout, QLabel, QPushButton, \
    QLineEdit
from PyQt5.QtGui import QIcon
from qgis.core import QgsProject
from qgis.gui import QgsProjectionSelectionWidget
from qgis.core import QgsPointXY
from typing import Dict, Optional
import logging

from . import resources
from .constants import (
    PLUGIN_DIR, UI_TEXTS, ERROR_MESSAGES, SUCCESS_MESSAGES,
    WMTS_LAYER_PREFIX, SUPPORTED_ENCODINGS
)
from .utils import ConfigManager, Validators, with_error_handling
from .core import LayerManager
from .widgets import SearchWidget, WfsWidget, SettingsWidget
from .config import API_KEY  # config.py에서 API_KEY 가져오기

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VWorld:
    """V-World QGIS 플러그인 메인 클래스"""

    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.plugin_dir = PLUGIN_DIR

        # 설정 관리자
        self.config = ConfigManager()

        # 위젯 인스턴스
        self.widgets: Dict[str, Optional[object]] = {
            'search': None,
            'wfs': None,
            'rgc': None,
            'geocoder': None,
            'encoding': None,
            'style': None
        }

        # 액션 목록
        self.actions = []

        # 메뉴 및 툴바
        self.menu = self.tr(UI_TEXTS['plugin_menu'])
        self.toolbar = self.iface.addToolBar(UI_TEXTS['toolbar_name'])
        self.toolbar.setObjectName(UI_TEXTS['toolbar_name'])

        # 번역 설정
        self._setup_translator()

        logger.info("VWorld 플러그인 초기화 완료")

    def _setup_translator(self):
        """
            번역기 설정
        """
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(self.plugin_dir, 'i18n', f'VWorld_{locale}.qm')

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)
            logger.info(f"번역 파일 로드 완료: {locale}")

    def tr(self, message: str) -> str:
        """
            메시지 번역
        """
        return QCoreApplication.translate('VWorld', message)

    def initGui(self):
        logger.info("GUI 초기화 중")

        # 지도 관련 액션
        self._add_map_actions()

        self.toolbar.addSeparator()

        # 레이어 관련 액션
        self._add_layer_actions()

        self.toolbar.addSeparator()

        # 검색 관련 액션
        self._add_search_actions()

        self.toolbar.addSeparator()

        # 도구 관련 액션
        self._add_tool_actions()

        self.toolbar.addSeparator()

        # 설정 액션
        self._add_action(
            ':/icon_setting',
            self.tr(UI_TEXTS['settings']),
            self._show_settings
        )

    def _add_map_actions(self):
        """
            지도 관련 액션 추가
        """
        map_actions = [
            (':/icon_base', UI_TEXTS['base_map'], 'Base'),
            (':/icon_satellite', UI_TEXTS['satellite_map'], 'Satellite'),
            (':/icon_hybrid', UI_TEXTS['hybrid_map'], 'Hybrid')
        ]

        for icon, text, layer_type in map_actions:
            self._add_action(
                icon,
                self.tr(text),
                lambda checked, lt=layer_type: self._add_wmts_layer(lt)
            )

    def _add_layer_actions(self):
        """
            레이어 관련 액션 추가
        """
        self._add_action(
            ':/icon_layer',
            self.tr(UI_TEXTS['wfs_layers']),
            self._show_wfs_widget
        )

        self._add_action(
            ':/icon_styleChange',
            self.tr(UI_TEXTS['style_change']),
            self._show_style_change
        )

    def _add_search_actions(self):
        """
            검색 관련 액션 추가
        """
        self._add_action(
            ':/icon_search',
            self.tr(UI_TEXTS['address_search']),
            self._show_search_widget
        )

        self._add_action(
            ':/icon_rgc',
            self.tr(UI_TEXTS['reverse_geocoding']),
            self._show_reverse_geocoding
        )

        self._add_action(
            ':/icon_geocoder',
            self.tr(UI_TEXTS['geocoding']),
            self._show_geocoder
        )

    def _add_tool_actions(self):
        """
            도구 관련 액션 추가
        """
        self._add_action(
            ':/icon_languages',
            self.tr(UI_TEXTS['encoding_change']),
            self._show_encoding_tool
        )

        self._add_action(
            ':/icon_mappingPoint',
            self.tr(UI_TEXTS['point_mapping']),
            self._show_point_mapping
        )

    def _add_action(self, icon_path: str, text: str, callback):
        """
            액션 추가
        """
        icon = QIcon(icon_path)
        action = QAction(icon, text, self.iface.mainWindow())
        action.triggered.connect(callback)

        self.toolbar.addAction(action)
        self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)

        return action

    @with_error_handling("WMTS 레이어 추가 중 오류가 발생했습니다")
    def _add_wmts_layer(self, layer_type: str):
        """
            WMTS 레이어 추가
        """
        # config.py의 API_KEY를 우선 확인
        if not API_KEY and not self.config.api_key:
            self.show_info_message("API 키 필요", ERROR_MESSAGES['api_key_missing'])
            self._show_settings()
            return

        LayerManager.add_wmts_layer(layer_type)
        self.show_info_message("성공", f"{layer_type} 레이어가 추가되었습니다.")

    def _show_widget(self, widget_class, widget_name: str, dock_area=Qt.LeftDockWidgetArea):
        """
            위젯 표시
        """
        if self.widgets[widget_name] is None:
            widget = widget_class(self.iface.mainWindow())
            self.widgets[widget_name] = widget

            if hasattr(widget, 'closingPlugin'):
                widget.closingPlugin.connect(
                    lambda: self._on_widget_closed(widget_name)
                )

            if hasattr(widget, 'setAllowedAreas'):
                self.iface.addDockWidget(dock_area, widget)

        self.widgets[widget_name].show()

    def _on_widget_closed(self, widget_name: str):
        """
            위젯 닫기 처리
        """
        if widget_name in self.widgets and self.widgets[widget_name]:
            widget = self.widgets[widget_name]
            if hasattr(widget, 'setParent'):
                self.iface.removeDockWidget(widget)
            widget.close()
            self.widgets[widget_name] = None
            logger.info(f"위젯 닫힘: {widget_name}")

    def _show_search_widget(self):
        """
            주소 검색 위젯 표시
        """
        self._show_widget(SearchWidget, 'search', Qt.LeftDockWidgetArea)

    def _show_wfs_widget(self):
        """
            WFS 위젯 표시
        """
        self._show_widget(WfsWidget, 'wfs', Qt.RightDockWidgetArea)

    def _show_settings(self):
        """
            설정 대화상자 표시
        """
        dialog = SettingsWidget(self.iface.mainWindow())
        dialog.exec_()

    def _show_reverse_geocoding(self):
        """
            역지오코딩 도구 표시
        """
        try:
            # Lazy import
            from .widgets.rgc_widget import ReverseGeocodingWidget

            if self.widgets['rgc'] is None:
                self.widgets['rgc'] = ReverseGeocodingWidget()
                self.widgets['rgc'].spotClick.clicked.connect(
                    self.widgets['rgc'].on_spot_clicked
                )

            self.widgets['rgc'].show()
        except ImportError:
            self.show_error_message("모듈 없음", "역지오코딩 위젯 모듈을 찾을 수 없습니다.")
            logger.error("ReverseGeocodingWidget 모듈을 찾을 수 없습니다")

    def _show_geocoder(self):
        """
            지오코더 표시
        """
        # config.py의 API_KEY를 우선 확인
        if not API_KEY and not self.config.api_key:
            self.show_info_message("API 키 필요", ERROR_MESSAGES['api_key_missing'])
            self._show_settings()
            return

        try:
            # Lazy import
            from .widgets.geocoder_widget import GeocoderWidget

            if self.widgets['geocoder'] is None:
                self.widgets['geocoder'] = GeocoderWidget()

            self.widgets['geocoder'].show()
        except ImportError:
            self.show_error_message("모듈 없음", "지오코더 위젯 모듈을 찾을 수 없습니다.")
            logger.error("GeocoderWidget 모듈을 찾을 수 없습니다")

    def _show_encoding_tool(self):
        """
            인코딩 변경 도구 표시
        """
        try:
            # Lazy import
            from .widgets.encoding_widget import EncodingWidget

            if self.widgets['encoding'] is None:
                self.widgets['encoding'] = EncodingWidget()

            self.widgets['encoding'].show()
            self.widgets['encoding'].refresh_layer_list()
        except ImportError:
            self.show_error_message("모듈 없음", "인코딩 위젯 모듈을 찾을 수 없습니다.")
            logger.error("EncodingWidget 모듈을 찾을 수 없습니다")

    def _show_style_change(self):
        """
            스타일 변경 도구 표시
        """
        try:
            # Lazy import
            from .widgets.style_widget import StyleChangeWidget

            if self.widgets['style'] is None:
                self.widgets['style'] = StyleChangeWidget()

            self.widgets['style'].show()
            self.widgets['style'].refresh_layer_list()
        except ImportError:
            self.show_error_message("모듈 없음", "스타일 변경 위젯 모듈을 찾을 수 없습니다.")
            logger.error("StyleChangeWidget 모듈을 찾을 수 없습니다")

    def _show_point_mapping(self):
        """
            포인트 매핑 도구 표시
        """
        dialog = QDialog(self.iface.mainWindow())
        dialog.setWindowTitle(UI_TEXTS['point_mapping'])
        dialog.resize(500, 200)

        layout = QVBoxLayout()

        # 좌표 입력
        coord_label = QLabel("좌표를 입력하세요:")
        coord_input = QLineEdit()
        coord_input.setPlaceholderText("경도 위도 경도 위도 ... (예: 127.5 37.5 128.0 38.0)")

        # 좌표계 선택
        crs_label = QLabel("좌표계를 선택하세요:")
        crs_selector = QgsProjectionSelectionWidget()

        # 저장 버튼
        save_button = QPushButton("저장")
        save_button.clicked.connect(
            lambda: self._process_point_mapping(
                coord_input.text(),
                crs_selector.crs().authid(),
                dialog
            )
        )

        layout.addWidget(coord_label)
        layout.addWidget(coord_input)
        layout.addWidget(crs_label)
        layout.addWidget(crs_selector)
        layout.addWidget(save_button)

        dialog.setLayout(layout)
        dialog.exec_()

    @with_error_handling("포인트 매핑 중 오류가 발생했습니다")
    def _process_point_mapping(self, coord_text: str, crs: str, dialog: QDialog):
        """
            포인트 매핑 처리
        """
        if not crs:
            self.show_warning_message("경고", "좌표계를 선택해주세요.")
            return

        try:
            # 좌표 검증
            coordinates = Validators.validate_coordinates(coord_text)

            # 레이어 생성
            layer = LayerManager.create_point_layer("포인트 매핑", crs)

            # 포인트 추가
            for lon, lat in coordinates:
                LayerManager.add_point_to_layer(layer, QgsPointXY(lon, lat))

            # 프로젝트에 추가
            QgsProject.instance().addMapLayer(layer)

            self.show_info_message("성공", f"{len(coordinates)}개의 포인트가 추가되었습니다.")
            dialog.close()

        except Exception as e:
            self.show_error_message("오류", str(e))

    def unload(self):
        """
            플러그인 언로드
        """
        logger.info("VWorld 플러그인 언로드 중")

        # 모든 액션 제거
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)

        # 툴바 제거
        del self.toolbar

        # 모든 위젯 닫기
        for widget_name, widget in self.widgets.items():
            if widget:
                if hasattr(widget, 'close'):
                    widget.close()
                self.widgets[widget_name] = None

        logger.info("VWorld 플러그인 언로드 완료")

    def show_info_message(self, title: str, message: str):
        """
            정보 메시지 표시
        """
        QMessageBox.information(self.iface.mainWindow(), title, message)

    def show_warning_message(self, title: str, message: str):
        """
            경고 메시지 표시
        """
        QMessageBox.warning(self.iface.mainWindow(), title, message)

    def show_error_message(self, title: str, message: str):
        """
            에러 메시지 표시
        """
        QMessageBox.critical(self.iface.mainWindow(), title, message)