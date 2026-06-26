from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import Qt, QSize, pyqtSignal
from qgis.PyQt.QtGui import QColor, QIcon, QPixmap
from qgis.utils import iface
from qgis.core import QgsPointXY

from ..constants import DATA_DIR, HEADER_STYLE_STANDARD, HEADER_STYLE_COMPACT
from ..utils import FileManager, ThemeColors, ConfigManager, feedback


class _UiHelpersMixin:
    """
        BaseWidget / BaseDialog 공통 UI·피드백 헬퍼.
        - 사용자 알림은 통합 feedback(메시지 바 우선)로 일원화.
        - 빈 상태 안내, 브랜드 헤더 등 화면 구성 헬퍼 공유.
    """

    def show_error_message(self, title: str, message: str):
        """ 에러 메시지 표시 - QGIS 메시지 바(비차단). """
        feedback.notify_error(title, message, self)

    def show_info_message(self, title: str, message: str):
        """ 정보 메시지 표시 - QGIS 메시지 바(비차단). """
        feedback.notify_info(title, message, self)

    def show_success_message(self, title: str, message: str):
        """ 성공 안내 표시 - 옵션 설정에 따라 팝업/메시지 바 전환. """
        feedback.notify_success(title, message, self)

    def show_warning_message(self, title: str, message: str):
        """ 경고 메시지 표시 - QGIS 메시지 바(비차단). """
        feedback.notify_warning(title, message, self)

    def show_question_message(self, title: str, message: str) -> bool:
        """ 질문 메시지 표시 - 사용자 결정이 필요하므로 차단 모달 유지. """
        return feedback.ask(self, title, message)

    def get_current_crs(self) -> str:
        """ 현재 프로젝트 좌표계 반환 """
        return self.canvas.mapSettings().destinationCrs().authid()

    def add_shortcut(self, key_sequence: str, callback, parent=None):
        """
            키보드 단축키 등록 (PyQt5/PyQt6 호환).
            parent 미지정 시 self에 바인딩. 파워 유저 효율을 위한 헬퍼.
        """
        try:
            from qgis.PyQt.QtGui import QShortcut, QKeySequence
        except ImportError:  # PyQt5는 QShortcut이 QtWidgets에 있음
            from qgis.PyQt.QtWidgets import QShortcut
            from qgis.PyQt.QtGui import QKeySequence
        shortcut = QShortcut(QKeySequence(key_sequence), parent or self)
        shortcut.activated.connect(callback)
        return shortcut

    def _set_list_placeholder(self, list_widget, text: str):
        """
            빈 리스트에 선택 불가능한 안내(빈 상태) 항목을 표시.
            처음 사용하는 사용자가 무엇을 할지 알 수 있도록 돕는다.
        """
        list_widget.clear()
        item = QtWidgets.QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setForeground(QColor(ThemeColors.muted()))
        list_widget.addItem(item)

    def make_brand_header(self, title: str, subtitle: str = "", icon_path: str = ""):
        """
            도크/다이얼로그 상단에 표시하는 브이월드 브랜드 색 헤더 스트립.
            QGIS 네이티브 외관을 유지하면서 플러그인 정체성을 부여한다.
            icon_path를 주면 기능별 아이콘을 왼쪽에 배치해 화면 간 구분을 돕는다.

            옵션의 '헤더 표시 모드'(표준/요약)에 따라 외형이 달라지며,
            apply_header_style()로 실행 중에도 다시 그릴 수 있다.
        """
        self._brand_header_params = (title, subtitle, icon_path)
        header = QtWidgets.QFrame()
        header.setObjectName("brandHeader")
        self._brand_header = header
        self._render_brand_header(header, self._current_header_style())
        return header

    @staticmethod
    def _current_header_style() -> str:
        """ 저장된 헤더 표시 모드 반환 (실패 시 표준). """
        try:
            return ConfigManager().header_style
        except Exception:
            return HEADER_STYLE_STANDARD

    def apply_header_style(self, style: str = None):
        """
            현재 위젯의 브랜드 헤더를 주어진 모드로 다시 그린다(실시간 반영).
            헤더가 없는 위젯에서는 조용히 무시한다.
        """
        header = getattr(self, '_brand_header', None)
        if header is None:
            return
        self._render_brand_header(header, style or self._current_header_style())

    def _render_brand_header(self, header, style: str):
        """
            header(QFrame) 내부를 모드에 맞게 (재)구성한다.
            동일 QFrame을 재사용하므로 레이아웃 내 위치가 유지된다.
        """
        # 기존 레이아웃·자식 정리 (재적용 대비) - 임시 위젯에 소유권 이전해 삭제 예약
        old_layout = header.layout()
        if old_layout is not None:
            QtWidgets.QWidget().setLayout(old_layout)

        title, subtitle, icon_path = getattr(
            self, '_brand_header_params', (header.windowTitle(), "", "")
        )
        compact = (style == HEADER_STYLE_COMPACT)

        brand = ThemeColors.brand()
        on_brand = ThemeColors.on_brand()
        header.setStyleSheet(f"#brandHeader {{ background: {brand}; }}")

        # 요약 모드는 더 얇은 스트립 + 작은 아이콘/제목, 부제목 생략
        margins = (12, 5, 12, 5) if compact else (14, 10, 14, 10)
        icon_px = 16 if compact else 22
        title_pt = 11 if compact else 13

        row = QtWidgets.QHBoxLayout(header)
        row.setContentsMargins(*margins)
        row.setSpacing(8 if compact else 10)

        # 기능별 아이콘 (흰색 틴트로 헤더 배경과 조화)
        if icon_path:
            icon = QIcon(icon_path)
            if not icon.isNull():
                pix = icon.pixmap(QSize(icon_px, icon_px))
                tinted = self._tint_pixmap(pix, on_brand)
                icon_lbl = QtWidgets.QLabel()
                icon_lbl.setPixmap(tinted)
                icon_lbl.setStyleSheet("background: transparent;")
                icon_lbl.setFixedWidth(icon_px + 2)
                row.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        text_col = QtWidgets.QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        title_lbl = QtWidgets.QLabel(title)
        title_lbl.setStyleSheet(
            f"font-size: {title_pt}pt; font-weight: 700; color: {on_brand}; background: transparent;"
        )
        text_col.addWidget(title_lbl)

        # 요약 모드에서는 부제목을 숨겨 공간을 절약한다
        if subtitle and not compact:
            sub_lbl = QtWidgets.QLabel(subtitle)
            sub_lbl.setStyleSheet(
                f"font-size: 9pt; color: {on_brand}; background: transparent;"
            )
            sub_lbl.setWordWrap(True)
            text_col.addWidget(sub_lbl)

        row.addLayout(text_col, 1)

    def make_section_title(self, text: str):
        """
            화면(페이지) 제목용 라벨. 전 위젯이 같은 스케일을 쓰도록 통일.
        """
        label = QtWidgets.QLabel(text)
        label.setStyleSheet("font-size: 14pt; font-weight: 700;")
        return label

    def make_section_caption(self, text: str):
        """
            구획(단계) 캡션용 라벨. 'N. 제목' 같은 소제목에 사용.
        """
        label = QtWidgets.QLabel(text)
        label.setStyleSheet("font-size: 11pt; font-weight: 600;")
        return label

    @staticmethod
    def _tint_pixmap(pixmap: QPixmap, color: str) -> QPixmap:
        """
            픽스맵의 알파를 유지하며 단색으로 칠한다(헤더 아이콘 흰색 틴트용).
        """
        if pixmap.isNull():
            return pixmap
        from qgis.PyQt.QtGui import QPainter
        tinted = QPixmap(pixmap.size())
        tinted.fill(Qt.GlobalColor.transparent)
        painter = QPainter(tinted)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), QColor(color))
        painter.end()
        return tinted


class BaseWidget(_UiHelpersMixin, QtWidgets.QDockWidget):
    """
        모든 Dock Widget의 기본 클래스
    """

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas = iface.mapCanvas()
        self.iface = iface
        self._setup_directories()

    def _setup_directories(self):
        """
            필요한 디렉토리 생성
        """
        FileManager.ensure_directory(DATA_DIR)

    def closeEvent(self, event):
        """
            위젯 닫기 이벤트
        """
        self.closingPlugin.emit()
        event.accept()

    def zoom_to_point(self, x: float, y: float, scale: int = 3000):
        """
            특정 지점으로 줌
        """
        center = QgsPointXY(x, y)
        self.canvas.setCenter(center)
        self.canvas.zoomScale(scale)
        self.canvas.refresh()

    def get_selected_items_from_list(self, list_widget) -> list:
        """
            리스트 위젯에서 선택된 아이템 가져오기
        """
        selected_items = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected_items.append(item)
        return selected_items


class BaseDialog(_UiHelpersMixin, QtWidgets.QDialog):
    """
        모든 Dialog의 기본 클래스
    """

    def __init__(self, parent=None, flags=Qt.WindowType.WindowStaysOnTopHint):
        super().__init__(parent, flags)
        self.canvas = iface.mapCanvas()
        self.iface = iface
