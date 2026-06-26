import logging

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QListWidgetItem, QListWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QPushButton, QAbstractItemView, QListView, QSizePolicy,
)
from qgis.core import QgsProject, QgsVectorLayer, QgsWkbTypes
from qgis.gui import QgsColorButton

from .base_widget import BaseDialog
from ..constants import ERROR_MESSAGES
from ..core import LayerManager
from ..utils import with_error_handling, with_loading_cursor, ThemeColors

logger = logging.getLogger(__name__)


def _is_polygon_vector(layer) -> bool:
    """벡터 레이어이면서 폴리곤 지오메트리인지 (QGIS 4 enum 호환) 판정."""
    if not isinstance(layer, QgsVectorLayer):
        return False
    polygon_geom_type = getattr(QgsWkbTypes, 'PolygonGeometry', None)
    if polygon_geom_type is None:
        polygon_geom_type = QgsWkbTypes.GeometryType.PolygonGeometry
    try:
        return layer.geometryType() == polygon_geom_type
    except Exception:
        return False


class StyleChangeWidget(BaseDialog):
    """
        폴리곤 레이어 외곽선 색상 일괄 변경 다이얼로그.
        - 프로젝트의 폴리곤 벡터 레이어 목록 표시(다중 선택)
        - '색상 랜덤' 체크 시 레이어마다 랜덤 색, 해제 시 선택한 색 적용
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._connect_signals()
        self.refresh_layer_list()
        self._update_color_button_state()

    def _build_ui(self):
        """코드로 UI 구성 (이전 v_world_dockStyleChange_base.ui 대체)."""
        self.setWindowTitle("스타일 변경")
        self.resize(482, 279)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(
            self.make_brand_header(
                "폴리곤 스타일 변경", "폴리곤 레이어 외곽선 색을 일괄 변경", ":/icon_styleChange"
            )
        )

        body = QVBoxLayout()
        body.setContentsMargins(16, 12, 16, 12)
        body.setSpacing(10)

        # 사용법 힌트
        hint = QLabel("폴리곤 레이어를 선택하고 색을 지정한 뒤 아래 버튼을 누르세요.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {ThemeColors.muted()};")
        body.addWidget(hint)

        # 레이어 목록
        self.layersList = QListWidget()
        self.layersList.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.layersList.setViewMode(QListView.ViewMode.ListMode)
        body.addWidget(self.layersList)

        # 색상 선택 행
        color_row = QHBoxLayout()
        self.label = QLabel("색상 선택")
        self.label.setMaximumWidth(50)
        color_row.addWidget(self.label)

        self.mColorButton = QgsColorButton()
        self.mColorButton.setMinimumSize(150, 16)
        color_row.addWidget(self.mColorButton)

        self.checkBox = QCheckBox("색상 랜덤")
        self.checkBox.setChecked(True)
        self.checkBox.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        color_row.addWidget(self.checkBox)
        body.addLayout(color_row)

        # 적용 버튼
        self.BTNstyleChange = QPushButton("폴리곤 스타일 변경하기")
        body.addWidget(self.BTNstyleChange)

        layout.addLayout(body)

    def _connect_signals(self):
        self.BTNstyleChange.clicked.connect(self._apply_style)
        self.checkBox.toggled.connect(
            lambda _checked=False: self._update_color_button_state()
        )

    def _update_color_button_state(self):
        """'색상 랜덤' 선택 시 색상 선택 위젯 비활성화."""
        use_random = self.checkBox.isChecked()
        if hasattr(self, 'mColorButton'):
            self.mColorButton.setEnabled(not use_random)
        if hasattr(self, 'label'):
            self.label.setEnabled(not use_random)

    def refresh_layer_list(self):
        """
            프로젝트의 폴리곤 벡터 레이어를 목록에 채움.
            기존 선택은 가능한 한 유지.
        """
        prev_selected = {
            it.data(Qt.ItemDataRole.UserRole)
            for it in self.layersList.selectedItems()
            if it.data(Qt.ItemDataRole.UserRole)
        }

        self.layersList.clear()

        polygon_layers = [
            lyr for lyr in QgsProject.instance().mapLayers().values()
            if _is_polygon_vector(lyr)
        ]

        if not polygon_layers:
            placeholder = QListWidgetItem("프로젝트에 폴리곤 레이어가 없습니다.")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.layersList.addItem(placeholder)
            return

        for lyr in polygon_layers:
            name = lyr.name()
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setToolTip(f"레이어: {name}\n소스: {lyr.source()}")
            if name in prev_selected:
                item.setSelected(True)
            self.layersList.addItem(item)

    @with_error_handling("스타일 변경 중 오류가 발생했습니다")
    @with_loading_cursor
    def _apply_style(self, checked=False):
        names = [
            it.data(Qt.ItemDataRole.UserRole)
            for it in self.layersList.selectedItems()
            if it.data(Qt.ItemDataRole.UserRole)
        ]

        if not names:
            self.show_warning_message("스타일 변경", ERROR_MESSAGES['no_layer_selected'])
            return

        use_random = self.checkBox.isChecked()
        color = None if use_random else self.mColorButton.color()

        styled = LayerManager.apply_polygon_style(names, color=color)

        if styled:
            self.show_success_message(
                "스타일 변경", f"폴리곤 레이어 {styled}개의 스타일을 변경했습니다."
            )
            logger.info(f"폴리곤 스타일 변경: {styled}개, 랜덤={use_random}")
        else:
            self.show_warning_message(
                "스타일 변경", "선택한 레이어 중 적용 가능한 폴리곤 레이어가 없습니다."
            )
