import re
import logging
from typing import List, Tuple

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QFrame,
)
from qgis.gui import QgsProjectionSelectionWidget
from qgis.core import (
    QgsProject, QgsPointXY, QgsCoordinateReferenceSystem,
)

from .base_widget import BaseDialog
from ..constants import DEFAULT_CRS
from ..utils import ThemeColors
from ..core import LayerManager

logger = logging.getLogger(__name__)

# 좌표 토큰 구분자 (콤마/세미콜론/공백/탭)
_SPLIT_RE = re.compile(r'[\s,;]+')


class PointMappingWidget(BaseDialog):
    """
        좌표 목록을 입력해 포인트 레이어를 생성하는 도구.
        다른 도구와 동일한 브랜드 헤더·단계 구성·힌트를 따른다(일관성).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        self.setWindowTitle("포인트 일괄 매핑")
        self.setMinimumSize(520, 480)
        self.resize(560, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        root.addWidget(
            self.make_brand_header(
                "포인트 일괄 매핑", "좌표 목록으로 포인트 레이어 만들기", ":/icon_mappingPoint"
            )
        )

        # 1. 좌표 입력
        root.addWidget(self.make_section_caption("1. 좌표 입력"))
        self.coordInput = QPlainTextEdit()
        self.coordInput.setAccessibleName("좌표 입력")
        self.coordInput.setPlaceholderText(
            "한 줄에 한 점씩 입력하세요 (경도 위도 순서)\n"
            "예)\n127.5 37.5\n128.0 38.0"
        )
        root.addWidget(self.coordInput, 1)

        hint = QLabel(
            "한 줄에 한 점씩, '경도 위도' 순서로 입력하세요. "
            "쉼표·공백 모두 인식합니다. 한 줄에 여러 쌍을 적어도 됩니다."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {ThemeColors.muted()};")
        root.addWidget(hint)

        # 2. 좌표계 선택
        root.addWidget(self.make_section_caption("2. 좌표계 선택"))
        crs_row = QHBoxLayout()
        crs_row.setSpacing(8)
        crs_label = QLabel("좌표계:")
        crs_row.addWidget(crs_label)
        self.crsSelector = QgsProjectionSelectionWidget()
        self._init_default_crs()
        crs_row.addWidget(self.crsSelector, 1)
        root.addLayout(crs_row)

        # 푸터
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(line)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.statusLabel = QLabel("")
        self.statusLabel.setWordWrap(True)
        footer.addWidget(self.statusLabel, 1)
        self.createBtn = QPushButton("포인트 만들기")
        self.createBtn.setMinimumHeight(32)
        f = self.createBtn.font()
        f.setBold(True)
        self.createBtn.setFont(f)
        self.createBtn.clicked.connect(self._on_create)
        footer.addWidget(self.createBtn)
        self.closeBtn = QPushButton("닫기")
        self.closeBtn.clicked.connect(self.accept)
        footer.addWidget(self.closeBtn)
        root.addLayout(footer)

    def _init_default_crs(self):
        """ 현재 프로젝트 좌표계를 기본 선택, 없으면 EPSG:4326. """
        try:
            crs = QgsProject.instance().crs()
            if crs is not None and crs.isValid():
                self.crsSelector.setCrs(crs)
                return
        except Exception:
            pass
        self.crsSelector.setCrs(QgsCoordinateReferenceSystem(DEFAULT_CRS))

    # ------------------------------------------------------------------
    # 파싱 / 생성
    # ------------------------------------------------------------------
    def _parse(self, text: str) -> Tuple[List[Tuple[float, float]], List[str]]:
        """ 입력 텍스트를 (좌표 리스트, 오류 메시지 리스트)로 변환. """
        points: List[Tuple[float, float]] = []
        errors: List[str] = []
        for line_no, raw in enumerate(text.splitlines(), 1):
            s = raw.strip()
            if not s:
                continue
            tokens = [t for t in _SPLIT_RE.split(s) if t]
            if len(tokens) % 2 != 0:
                errors.append(f"{line_no}행: 좌표는 쌍(경도 위도)이어야 합니다 → '{s}'")
                continue
            try:
                for i in range(0, len(tokens), 2):
                    lon = float(tokens[i])
                    lat = float(tokens[i + 1])
                    points.append((lon, lat))
            except ValueError:
                errors.append(f"{line_no}행: 숫자로 읽을 수 없습니다 → '{s}'")
        return points, errors

    def _on_create(self, checked=False):
        crs = self.crsSelector.crs().authid()
        if not crs:
            self._flash("좌표계를 선택해주세요.", level='warn')
            return

        text = self.coordInput.toPlainText()
        points, errors = self._parse(text)

        if not points:
            if errors:
                self._flash(
                    f"좌표를 읽지 못했습니다. {errors[0]}", level='warn'
                )
            else:
                self._flash(
                    "입력된 좌표가 없습니다. '경도 위도' 형식으로 입력해주세요.",
                    level='warn',
                )
            return

        try:
            layer = LayerManager.create_point_layer("포인트 매핑", crs)
            for lon, lat in points:
                LayerManager.add_point_to_layer(layer, QgsPointXY(lon, lat))
            QgsProject.instance().addMapLayer(layer)
        except Exception as e:
            logger.exception("포인트 레이어 생성 실패")
            self._flash(f"레이어 생성에 실패했습니다: {e}", level='error')
            self.show_error_message("포인트 매핑 오류", str(e))
            return

        skipped = len(errors)
        msg = f"좌표 {len(points)}개를 포인트 레이어로 추가했습니다."
        if skipped:
            msg += f" (형식 오류 {skipped}줄은 건너뜀)"
        self.show_success_message("포인트 매핑", msg)
        self.accept()

    # ------------------------------------------------------------------
    # 상태 표시 (오류는 자동으로 사라지지 않음 — 초보자가 읽을 시간 확보)
    # ------------------------------------------------------------------
    def _flash(self, message: str, level: str = 'info'):
        color = ThemeColors.status_info()
        if level == 'warn':
            color = ThemeColors.status_warn()
        elif level == 'error':
            color = ThemeColors.status_error()
        self.statusLabel.setStyleSheet(f"color: {color};")
        self.statusLabel.setText(message)
