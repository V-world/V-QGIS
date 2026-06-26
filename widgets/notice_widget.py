from datetime import date, timedelta
import logging

from qgis.PyQt.QtCore import Qt, QUrl, pyqtSignal
from qgis.PyQt.QtGui import QPixmap, QDesktopServices, QCursor
from qgis.PyQt.QtWidgets import (
    QLabel, QCheckBox, QPushButton, QVBoxLayout, QHBoxLayout
)

from .base_widget import BaseDialog
from ..constants import UI_TEXTS, NOTICE_BLOG_BASE
from ..utils import ConfigManager

logger = logging.getLogger(__name__)

MAX_IMAGE_WIDTH = 600
HIDE_DAYS = 7


class _ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class NoticeDialog(BaseDialog):
    """
        시작 공지 팝업 - 이미지 클릭 시 해당 글을 기본 브라우저로 연다.
        '오늘 하루 보지 않기' 체크 시 오늘 날짜를 저장한다.
    """

    def __init__(self, image_bytes, link, parent=None):
        super().__init__(parent)
        self.link = link or NOTICE_BLOG_BASE
        self.config = ConfigManager()

        pixmap = QPixmap()
        pixmap.loadFromData(image_bytes)
        self.valid = not pixmap.isNull()
        if pixmap.width() > MAX_IMAGE_WIDTH:
            pixmap = pixmap.scaledToWidth(
                MAX_IMAGE_WIDTH, Qt.TransformationMode.SmoothTransformation
            )

        self.setWindowTitle(UI_TEXTS['notice_title'])

        layout = QVBoxLayout(self)

        image_label = _ClickableLabel()
        image_label.setPixmap(pixmap)
        image_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        image_label.setToolTip(self.link)
        image_label.clicked.connect(self._open_link)
        layout.addWidget(image_label)

        bottom = QHBoxLayout()
        self.hide_week_cb = QCheckBox(UI_TEXTS['notice_hide_week'])
        bottom.addWidget(self.hide_week_cb)
        bottom.addStretch()
        close_btn = QPushButton(UI_TEXTS['notice_close'])
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

        self.adjustSize()

    def _open_link(self):
        # 이미지 클릭 시 링크를 열고 팝업을 닫는다.
        QDesktopServices.openUrl(QUrl(self.link))
        self.accept()

    def _save_hide_preference(self):
        if self.hide_week_cb.isChecked():
            until = date.today() + timedelta(days=HIDE_DAYS)
            self.config.notice_hide_until = until.isoformat()

    def accept(self):
        self._save_hide_preference()
        super().accept()

    def closeEvent(self, event):
        self._save_hide_preference()
        super().closeEvent(event)
