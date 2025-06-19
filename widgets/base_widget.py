from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.utils import iface
from qgis.core import QgsPointXY
from typing import Optional, Dict, Any
import logging

from ..constants import DATA_DIR, ERROR_MESSAGES, SUCCESS_MESSAGES
from ..utils import FileManager

logger = logging.getLogger(__name__)


class BaseWidget(QtWidgets.QDockWidget):
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

    def show_error_message(self, title: str, message: str):
        """
            에러 메시지 표시
        """
        QtWidgets.QMessageBox.critical(self, title, message)
        logger.error(f"{title}: {message}")

    def show_info_message(self, title: str, message: str):
        """
            정보 메시지 표시
        """
        QtWidgets.QMessageBox.information(self, title, message)
        logger.info(f"{title}: {message}")

    def show_warning_message(self, title: str, message: str):
        """
            경고 메시지 표시
        """
        QtWidgets.QMessageBox.warning(self, title, message)
        logger.warning(f"{title}: {message}")

    def show_question_message(self, title: str, message: str) -> bool:
        """
            질문 메시지 표시
        """
        reply = QtWidgets.QMessageBox.question(
            self, title, message,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        return reply == QtWidgets.QMessageBox.Yes

    def closeEvent(self, event):
        """
            위젯 닫기 이벤트
        """
        self.closingPlugin.emit()
        event.accept()

    def get_current_crs(self) -> str:
        """
            현재 프로젝트 좌표계 반환
        """
        return self.canvas.mapSettings().destinationCrs().authid()

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
            if item.checkState() == Qt.Checked:
                selected_items.append(item)
        return selected_items


class BaseDialog(QtWidgets.QDialog):
    """
        모든 Dialog의 기본 클래스
    """

    def __init__(self, parent=None, flags=Qt.WindowStaysOnTopHint):
        super().__init__(parent, flags)
        self.canvas = iface.mapCanvas()
        self.iface = iface

    def show_error_message(self, title: str, message: str):
        """
            에러 메시지 표시
        """
        QtWidgets.QMessageBox.critical(self, title, message)
        logger.error(f"{title}: {message}")

    def show_info_message(self, title: str, message: str):
        """
            정보 메시지 표시
        """
        QtWidgets.QMessageBox.information(self, title, message)
        logger.info(f"{title}: {message}")

    def show_warning_message(self, title: str, message: str):
        """
            경고 메시지 표시
        """
        QtWidgets.QMessageBox.warning(self, title, message)
        logger.warning(f"{title}: {message}")

    def get_current_crs(self) -> str:
        """
            현재 프로젝트 좌표계 반환
        """
        return self.canvas.mapSettings().destinationCrs().authid()