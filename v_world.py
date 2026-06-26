import platform
from qgis.PyQt.QtCore import QCoreApplication, Qt, QTimer, QUrl
from qgis.PyQt.QtWidgets import QAction, QMenu, QFileDialog, QDialog, QVBoxLayout, QLabel, QPushButton, \
    QLineEdit
from qgis.PyQt.QtGui import QIcon, QDesktopServices
from qgis.core import QgsProject, Qgis
from qgis.gui import QgsProjectionSelectionWidget
from qgis.core import QgsPointXY
from typing import Dict, Optional
from datetime import date
import logging

from . import resources
from .constants import (
    PLUGIN_DIR, PLUGIN_VERSION, UI_TEXTS, ERROR_MESSAGES, SUCCESS_MESSAGES,
    WMTS_LAYER_PREFIX, SUPPORTED_ENCODINGS,
    TOOLBAR_DISPLAY_MODES, DEFAULT_TOOLBAR_DISPLAY_MODE,
    NOTICE_BLOG_BASE
)
from .utils import ConfigManager, Validators, with_error_handling, feedback
from .core import LayerManager, NoticeWorker
from .widgets import SearchWidget, WfsWidget, SettingsWidget, NoticeDialog, OnboardingWidget
from .config import API_KEY  # config.py에서 API_KEY 가져오기

# 패널/파일 로깅은 utils.logger가 패키지 루트 로거에 설치한 핸들러가 담당한다.
# (logging.basicConfig는 QGIS 전체 루트 로거를 건드리므로 사용하지 않는다)
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
            'style': None,
            'onboarding': None,
            'point': None,
            # 'admin_split': None
        }

        # 액션 목록
        self.actions = []

        # 시작 공지 팝업 (백그라운드 워커/다이얼로그 참조 유지)
        self._notice_worker = None
        self._notice_dialog = None
        self._notice_started = False

        # 메뉴 및 툴바
        self.menu = self.tr(UI_TEXTS['plugin_menu'])
        self.toolbar = self.iface.addToolBar(UI_TEXTS['toolbar_name'])
        self.toolbar.setObjectName(UI_TEXTS['toolbar_name'])

        # 환경 정보 - 사용자가 보낸 로그 파일 첫머리에서 환경을 바로 파악할 수 있게 기록
        logger.info(
            f"VWorld 플러그인 초기화 완료 "
            f"(플러그인 v{PLUGIN_VERSION}, QGIS {Qgis.QGIS_VERSION}, "
            f"{platform.platform()}, Python {platform.python_version()})"
        )

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

        # 시작하기(도움말) - 툴바 혼잡을 피해 플러그인 메뉴에만 추가(재실행 경로)
        self._add_menu_action(
            ':/icon_base',
            "시작하기",
            self._show_onboarding,
        )

        # 저장된 툴바 표시 모드 적용
        self._apply_toolbar_style()

        # 시작 공지 팝업
        self._maybe_show_notice()

        # 최초 실행 시작하기 패널
        self._maybe_show_onboarding()

    def _maybe_show_notice(self):
        """
            시작 공지 팝업 예약 - QGIS 로딩이 끝난 뒤에 로드한다.
            '일주일간 보지 않기' 기간이면 건너뛴다.
            실패해도 QGIS 시작을 방해하지 않도록 예외를 흡수한다.
        """
        try:
            hide_until = self.config.notice_hide_until
            if hide_until and date.today().isoformat() <= hide_until:
                return
            # QGIS 초기화 완료 후 로드(로딩 중 팝업 방지). 리로드 대비 타이머 폴백.
            try:
                self.iface.initializationCompleted.connect(self._start_notice_load)
            except Exception:
                pass
            QTimer.singleShot(5000, self._start_notice_load)
        except Exception as e:
            logger.info(f"공지 초기화 건너뜀: {e}")

    def _start_notice_load(self):
        """
            공지 백그라운드 로드 시작 (initializationCompleted 또는 폴백 타이머에서 1회만 실행)
        """
        if self._notice_started:
            return
        self._notice_started = True
        try:
            self.iface.initializationCompleted.disconnect(self._start_notice_load)
        except Exception:
            pass
        try:
            self._notice_worker = NoticeWorker()
            self._notice_worker.finished.connect(self._on_notice_ready)
            self._notice_worker.failed.connect(
                lambda msg: logger.info(f"공지 로드 건너뜀: {msg}")
            )
            self._notice_worker.start()
        except Exception as e:
            logger.info(f"공지 로드 시작 실패: {e}")

    def _on_notice_ready(self, data: dict):
        """
            공지 데이터 수신 시 팝업 표시
        """
        if not data or not data.get('image_bytes'):
            return
        try:
            dialog = NoticeDialog(
                data['image_bytes'],
                data.get('link', NOTICE_BLOG_BASE),
                self.iface.mainWindow()
            )
            if not dialog.valid:
                return
            self._notice_dialog = dialog
            dialog.exec()
        except Exception as e:
            logger.info(f"공지 표시 건너뜀: {e}")

    def _apply_toolbar_style(self):
        """
            저장된 툴바 표시 모드 적용
        """
        mode = self.config.toolbar_display_mode
        style, _label = TOOLBAR_DISPLAY_MODES.get(
            mode, TOOLBAR_DISPLAY_MODES[DEFAULT_TOOLBAR_DISPLAY_MODE]
        )
        self.toolbar.setToolButtonStyle(style)

    def _on_toolbar_style_changed(self, mode_key: str):
        """
            옵션 창에서 툴바 모드 변경 시 실시간 반영
        """
        try:
            style, _label = TOOLBAR_DISPLAY_MODES.get(
                mode_key, TOOLBAR_DISPLAY_MODES[DEFAULT_TOOLBAR_DISPLAY_MODE]
            )
            self.toolbar.setToolButtonStyle(style)
            logger.info(f"툴바 스타일 적용: {mode_key} -> {style}")
        except Exception:
            logger.exception(f"툴바 스타일 실시간 반영 실패 (mode={mode_key})")

    def _on_header_style_changed(self, style: str):
        """
            옵션 창에서 헤더 표시 모드 변경 시, 열려 있는 모든 패널에 실시간 반영
        """
        for widget in self.widgets.values():
            if widget is not None and hasattr(widget, 'apply_header_style'):
                try:
                    widget.apply_header_style(style)
                except Exception:
                    logger.exception("헤더 스타일 실시간 반영 실패")

    def _add_map_actions(self):
        """
            배경지도 액션 추가 (일반·항공·하이브리드를 각각 개별 버튼으로).
        """
        map_actions = [
            (':/icon_base', UI_TEXTS['base_map'], 'Base',
             "브이월드 일반지도를 지도에 추가합니다."),
            (':/icon_satellite', UI_TEXTS['satellite_map'], 'Satellite',
             "브이월드 항공(위성)지도를 지도에 추가합니다."),
            (':/icon_hybrid', UI_TEXTS['hybrid_map'], 'Hybrid',
             "브이월드 하이브리드(항공+지명) 지도를 지도에 추가합니다."),
        ]

        for icon, text, layer_type, tip in map_actions:
            self._add_action(
                icon,
                self.tr(text),
                lambda checked, lt=layer_type: self._add_wmts_layer(lt),
                tooltip=tip,
            )

    def _add_layer_actions(self):
        """
            레이어 관련 액션 추가
        """
        self._add_action(
            ':/icon_layer',
            self.tr(UI_TEXTS['wfs_layers']),
            self._show_wfs_widget,
            tooltip="국가 공간정보 주제도를 검색·즐겨찾기하고 지도에 추가합니다."
        )

        self._add_action(
            ':/icon_styleChange',
            self.tr(UI_TEXTS['style_change']),
            self._show_style_change,
            tooltip="지적도 등 폴리곤 레이어의 외곽선 스타일·라벨을 일괄 적용합니다."
        )

    def _add_search_actions(self):
        """
            검색 관련 액션 추가
        """
        self._add_action(
            ':/icon_search',
            self.tr(UI_TEXTS['address_search']),
            self._show_search_widget,
            tooltip="도로명·지번 주소를 검색해 지도로 이동합니다."
        )

        self._add_action(
            ':/icon_rgc',
            self.tr(UI_TEXTS['reverse_geocoding']),
            self._show_reverse_geocoding,
            tooltip="지도에서 클릭한 위치의 주소를 확인합니다. (역지오코딩)"
        )

        self._add_action(
            ':/icon_geocoder',
            self.tr(UI_TEXTS['geocoding']),
            self._show_geocoder,
            tooltip="엑셀·CSV의 주소 목록을 좌표로 일괄 변환합니다. (본인 인증키 필요)"
        )

    def _add_tool_actions(self):
        """
            도구 관련 액션 추가
        """
        self._add_action(
            ':/icon_languages',
            self.tr(UI_TEXTS['encoding_change']),
            self._show_encoding_tool,
            tooltip="레이어 인코딩을 UTF-8·EUC-KR·CP949·MS949로 전환합니다."
        )

        self._add_action(
            ':/icon_mappingPoint',
            self.tr(UI_TEXTS['point_mapping']),
            self._show_point_mapping,
            tooltip="좌표 목록을 입력해 포인트 레이어를 만듭니다."
        )

        # self._add_action(
        #     ':/icon_layer',
        #     self.tr(UI_TEXTS['admin_split']),
        #     self._show_admin_split,
        #     tooltip="대상 레이어를 광역시도·시군구·읍면동 단위로 분할합니다."
        # )

    def _add_action(self, icon_path: str, text: str, callback, tooltip: str = ""):
        """
            액션 추가. tooltip을 주면 마우스 오버·상태바에 쉬운 말 설명을 표시한다.
        """
        icon = QIcon(icon_path)
        action = QAction(icon, text, self.iface.mainWindow())
        action.triggered.connect(callback)
        if tooltip:
            action.setToolTip(tooltip)
            action.setStatusTip(tooltip)

        self.toolbar.addAction(action)
        self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)

        return action

    def _add_menu_action(self, icon_path: str, text: str, callback):
        """
            툴바에는 넣지 않고 플러그인 메뉴에만 추가하는 액션.
            (툴바 인지 부하를 늘리지 않으면서 재실행 경로를 제공)
        """
        icon = QIcon(icon_path)
        action = QAction(icon, text, self.iface.mainWindow())
        action.triggered.connect(callback)
        self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)
        return action

    def _maybe_show_onboarding(self):
        """
            시작 시 '시작하기' 안내 팝업을 자동으로 띄운다.
            사용자가 '다음부터 표시하지 않기'를 선택한 경우에만 건너뛴다.
            (한 번 봤다고 영구히 숨기지 않는다 — 체크박스 의미와 일치)
            실패해도 QGIS 시작을 방해하지 않도록 예외를 흡수한다.
        """
        try:
            if self.config.onboarding_hide:
                return
            # QGIS 로딩 직후 잠깐 뒤에 표시(로딩 중 깜빡임 방지).
            QTimer.singleShot(800, self._show_onboarding)
        except Exception as e:
            logger.info(f"시작하기 패널 초기화 건너뜀: {e}")

    def _show_onboarding(self, checked=False):
        """
            '시작하기' 안내 팝업 표시(비모달 + 항상 위).
            주요 동작을 콜백으로 연결한다. 모달이 아니므로 사용자는 본화면을 조작할 수 있다.
        """
        self.config.onboarding_seen = True
        try:
            if self.widgets.get('onboarding') is None:
                self.widgets['onboarding'] = OnboardingWidget(
                    callbacks={
                        'issue_key': self._open_issue_key_page,
                        'open_settings': self._show_settings,
                        'add_basemap': lambda: self._add_wmts_layer('Base'),
                        'open_search': self._show_search_widget,
                    },
                    parent=self.iface.mainWindow(),

                )

            widget = self.widgets['onboarding']
            widget.refresh_status()
            widget.show()
            widget.raise_()
            widget.activateWindow()
        except Exception:
            logger.exception("시작하기 팝업 표시 실패")
            self.show_error_message(
                "시작하기 오류",
                "시작하기 안내를 열 수 없습니다. QGIS 로그를 확인해 주세요."
            )

    def _open_issue_key_page(self):
        """ 브이월드 오픈API 인증키 발급 페이지 열기. """
        QDesktopServices.openUrl(QUrl("https://www.vworld.kr/dev/v4api.do"))

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
        names = {'Base': '일반지도', 'Satellite': '항공지도', 'Hybrid': '하이브리드'}
        label = names.get(layer_type, layer_type)
        self.show_success_message("배경지도 추가", f"브이월드 {label}를 추가했습니다.")

    def _show_widget(self, widget_class, widget_name: str, dock_area=Qt.DockWidgetArea.LeftDockWidgetArea):
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
        self._show_widget(SearchWidget, 'search', Qt.DockWidgetArea.LeftDockWidgetArea)

    def _show_wfs_widget(self):
        """
            WFS 위젯 표시
        """
        self._show_widget(WfsWidget, 'wfs', Qt.DockWidgetArea.RightDockWidgetArea)

    def _show_settings(self):
        """
            설정 대화상자 표시
        """
        dialog = SettingsWidget(self.iface.mainWindow())
        dialog.toolbarStyleChanged.connect(self._on_toolbar_style_changed)
        dialog.headerStyleChanged.connect(self._on_header_style_changed)
        dialog.exec()

    def _show_reverse_geocoding(self):
        """
            역지오코딩 도구 표시
        """
        try:
            # Lazy import
            from .widgets.rgc_widget import ReverseGeocodingWidget

            # 공통 헬퍼로 메인 윈도우를 부모로 지정해 일관되게 표시(생명주기·스태킹 통일)
            self._show_widget(
                ReverseGeocodingWidget, 'rgc', Qt.DockWidgetArea.LeftDockWidgetArea
            )
        except ImportError:
            self.show_error_message("모듈 없음", "역지오코딩 위젯 모듈을 찾을 수 없습니다.")
            logger.error("ReverseGeocodingWidget 모듈을 찾을 수 없습니다")

    def _show_geocoder(self):
        """
            지오코더 표시 - 사용자 본인 API 키 필수 (config.py 키 무시)
        """
        if not self.config.user_api_key:
            self.show_info_message(
                "사용자 API 키 필요",
                ERROR_MESSAGES['user_api_key_missing']
            )
            self._show_settings()
            return

        try:
            # Lazy import
            from .widgets.geocoder_widget import GeocoderWidget

            if self.widgets['geocoder'] is None:
                self.widgets['geocoder'] = GeocoderWidget(self.iface.mainWindow())

            self.widgets['geocoder'].show()
            self.widgets['geocoder'].raise_()
            self.widgets['geocoder'].activateWindow()
        except Exception as e:
            self.show_error_message(
                "지오코더 오류",
                "지오코더를 열 수 없습니다. 잠시 후 다시 시도해 주세요. "
                "문제가 계속되면 QGIS 로그를 확인하세요."
            )
            logger.exception("GeocoderWidget 로드 실패")

    def _show_encoding_tool(self):
        """
            인코딩 변경 도구 표시
        """
        try:
            # Lazy import
            from .widgets.encoding_widget import EncodingWidget

            # 공통 헬퍼로 메인 윈도우 부모 지정해 일관 표시 후 레이어 목록 새로고침
            self._show_widget(
                EncodingWidget, 'encoding', Qt.DockWidgetArea.LeftDockWidgetArea
            )
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

            # 공통 헬퍼로 메인 윈도우 부모 지정해 일관 표시 후 레이어 목록 새로고침
            self._show_widget(
                StyleChangeWidget, 'style', Qt.DockWidgetArea.LeftDockWidgetArea
            )
            self.widgets['style'].refresh_layer_list()
        except Exception:
            self.show_error_message(
                "스타일 변경 오류",
                "스타일 변경 도구를 열 수 없습니다. 잠시 후 다시 시도해 주세요. "
                "문제가 계속되면 QGIS 로그를 확인하세요."
            )
            logger.exception("StyleChangeWidget 로드 실패")

    def _show_admin_split(self):
        """
            행정구역 분할 도구 표시.
            대상 레이어를 광역시도·시군구·읍면동 단위로 잘라 그룹 레이어로 만든다.
        """
        # try:
        #     # Lazy import
        #     from .widgets.admin_split_widget import AdminSplitWidget
        #
        #     self._show_widget(
        #         AdminSplitWidget, 'admin_split', Qt.DockWidgetArea.LeftDockWidgetArea
        #     )
        #     self.widgets['admin_split'].refresh_layer_list()
        # except Exception:
        #     self.show_error_message(
        #         "행정구역 분할 오류",
        #         "행정구역 분할 도구를 열 수 없습니다. 잠시 후 다시 시도해 주세요. "
        #         "문제가 계속되면 QGIS 로그를 확인하세요."
        #     )
        #     logger.exception("AdminSplitWidget 로드 실패")

    def _show_point_mapping(self):
        """
            포인트 일괄 매핑 도구 표시.
            다른 도구와 동일한 패턴(브랜드 헤더·단계·힌트)을 따르는 전용 위젯 사용.
        """
        try:
            # Lazy import
            from .widgets.point_mapping_widget import PointMappingWidget

            if self.widgets.get('point') is None:
                self.widgets['point'] = PointMappingWidget(self.iface.mainWindow())

            self.widgets['point'].show()
            self.widgets['point'].raise_()
            self.widgets['point'].activateWindow()
        except Exception:
            self.show_error_message(
                "포인트 매핑 오류",
                "포인트 매핑 도구를 열 수 없습니다. 잠시 후 다시 시도해 주세요. "
                "문제가 계속되면 QGIS 로그를 확인하세요."
            )
            logger.exception("PointMappingWidget 로드 실패")

    def unload(self):
        """
            플러그인 언로드
        """
        logger.info("VWorld 플러그인 언로드 중")

        # 시작 공지 워커/다이얼로그 정리
        if self._notice_worker is not None:
            try:
                if self._notice_worker.isRunning():
                    self._notice_worker.quit()
                    self._notice_worker.wait(2000)
            except Exception:
                pass
            self._notice_worker = None
        if self._notice_dialog is not None:
            try:
                self._notice_dialog.close()
            except Exception:
                pass
            self._notice_dialog = None

        # 모든 액션 제거
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)
        self.actions = []

        # 툴바 제거 - 메인 윈도우에서 떼어내고 즉시 파괴.
        # deleteLater()는 비동기라 리로드(unload→initGui 연속 호출) 시
        # 이전 툴바가 살아 있어 objectName 중복 경고가 난다 → sip.delete로 동기 삭제.
        if self.toolbar is not None:
            try:
                from qgis.PyQt import sip
            except ImportError:
                import sip
            self.iface.mainWindow().removeToolBar(self.toolbar)
            if not sip.isdeleted(self.toolbar):
                sip.delete(self.toolbar)
            self.toolbar = None

        # 모든 위젯 닫기 (Dock 위젯은 메인 윈도우에서도 제거)
        for widget_name, widget in self.widgets.items():
            if widget:
                if hasattr(widget, 'setAllowedAreas'):
                    self.iface.removeDockWidget(widget)
                if hasattr(widget, 'close'):
                    widget.close()
                self.widgets[widget_name] = None

        logger.info("VWorld 플러그인 언로드 완료")

    def show_info_message(self, title: str, message: str):
        """
            정보 메시지 표시 - QGIS 메시지 바(비차단).
        """
        feedback.notify_info(title, message, self.iface.mainWindow())

    def show_success_message(self, title: str, message: str):
        """
            성공 안내 표시 - 옵션 설정에 따라 팝업/메시지 바 전환.
        """
        feedback.notify_success(title, message, self.iface.mainWindow())

    def show_warning_message(self, title: str, message: str):
        """
            경고 메시지 표시 - QGIS 메시지 바(비차단).
        """
        feedback.notify_warning(title, message, self.iface.mainWindow())

    def show_error_message(self, title: str, message: str):
        """
            에러 메시지 표시 - QGIS 메시지 바(비차단).
        """
        feedback.notify_error(title, message, self.iface.mainWindow())