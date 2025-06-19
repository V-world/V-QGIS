import os
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QPushButton, QLabel, QLineEdit
from qgis.core import QgsPointXY, QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsProject
from qgis.gui import QgsMapToolEmitPoint
import logging

from .base_widget import BaseDialog
from ..constants import UI_DIR
from ..utils import ApiClient, with_error_handling, require_api_key
from ..config import API_KEY

logger = logging.getLogger(__name__)

# UI 파일이 있는 경우 사용, 없으면 동적 생성
try:
    FORM_CLASS, _ = uic.loadUiType(os.path.join(UI_DIR, 'v_world_reverse_geocoding_base.ui'))
except:
    FORM_CLASS = None


class PointTool(QgsMapToolEmitPoint):
    """
        지도에서 포인트 선택 도구
    """

    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas

    def canvasReleaseEvent(self, event):
        """
        마우스 릴리즈 이벤트
        """
        point = self.toMapCoordinates(event.pos())
        self.canvasClicked.emit(point, event.button())


class ReverseGeocodingWidget(BaseDialog, FORM_CLASS if FORM_CLASS else object):
    """
        역지오코딩 위젯
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        if FORM_CLASS:
            self.setupUi(self)
        else:
            self._setup_ui()

        self.api_client = ApiClient()
        self.point_tool = None
        self._connect_signals()

    def _setup_ui(self):
        """
            UI 동적 생성 (UI 파일이 없는 경우)
        """
        self.setWindowTitle("주소 조회")
        self.resize(400, 200)

        from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGroupBox

        layout = QVBoxLayout()

        # 좌표 입력 그룹
        coord_group = QGroupBox("좌표 입력")
        coord_layout = QVBoxLayout()

        # X 좌표
        x_layout = QHBoxLayout()
        x_layout.addWidget(QLabel("X 좌표:"))
        self.xInput = QLineEdit()
        x_layout.addWidget(self.xInput)
        coord_layout.addLayout(x_layout)

        # Y 좌표
        y_layout = QHBoxLayout()
        y_layout.addWidget(QLabel("Y 좌표:"))
        self.yInput = QLineEdit()
        y_layout.addWidget(self.yInput)
        coord_layout.addLayout(y_layout)

        # 좌표계
        crs_layout = QHBoxLayout()
        crs_layout.addWidget(QLabel("좌표계:"))
        self.crsSelect = QLineEdit("EPSG:4326")
        crs_layout.addWidget(self.crsSelect)
        coord_layout.addLayout(crs_layout)

        coord_group.setLayout(coord_layout)
        layout.addWidget(coord_group)

        # 버튼
        button_layout = QHBoxLayout()
        self.spotClick = QPushButton("지도에서 선택")
        self.searchButton = QPushButton("주소 조회")
        button_layout.addWidget(self.spotClick)
        button_layout.addWidget(self.searchButton)
        layout.addLayout(button_layout)

        # 결과
        result_group = QGroupBox("조회 결과")
        result_layout = QVBoxLayout()
        self.resultLabel = QLabel("결과가 여기에 표시됩니다.")
        result_layout.addWidget(self.resultLabel)
        result_group.setLayout(result_layout)
        layout.addWidget(result_group)

        self.setLayout(layout)

    def _connect_signals(self):
        """
            시그널 연결
        """
        if hasattr(self, 'searchButton'):
            self.searchButton.clicked.connect(self._on_search_clicked)
        if hasattr(self, 'spotClick'):
            self.spotClick.clicked.connect(self.on_spot_clicked)

    def on_spot_clicked(self):
        """
            지도에서 선택 버튼 클릭
        """
        if self.point_tool is None:
            self.point_tool = PointTool(self.canvas)
            self.point_tool.canvasClicked.connect(self._on_map_clicked)

        self.canvas.setMapTool(self.point_tool)
        self.hide()  # 위젯 숨기기

    def _on_map_clicked(self, point: QgsPointXY, button):
        """
            지도 클릭 시 처리
        """
        if button == Qt.LeftButton:
            # 현재 프로젝트 좌표계
            project_crs = self.canvas.mapSettings().destinationCrs()

            # EPSG:4326으로 변환
            if project_crs.authid() != "EPSG:4326":
                transform = QgsCoordinateTransform(
                    project_crs,
                    QgsCoordinateReferenceSystem("EPSG:4326"),
                    QgsProject.instance()
                )
                point = transform.transform(point)

            # 좌표 입력
            self.xInput.setText(f"{point.x():.6f}")
            self.yInput.setText(f"{point.y():.6f}")
            self.crsSelect.setText("EPSG:4326")

            # 위젯 다시 표시
            self.show()

            # 기본 맵 도구로 복원
            self.canvas.unsetMapTool(self.point_tool)

            # 자동으로 주소 조회
            self._on_search_clicked()

    @with_error_handling("역지오코딩 중 오류가 발생했습니다")
    @require_api_key
    def _on_search_clicked(self):
        """
            주소 조회 버튼 클릭
        """
        try:
            x = float(self.xInput.text())
            y = float(self.yInput.text())
            crs = self.crsSelect.text() if hasattr(self, 'crsSelect') else "EPSG:4326"

            # 역지오코딩 수행
            response = self.api_client.reverse_geocode(x, y, crs)

            if response.get('response', {}).get('status') == 'OK':
                result = response['response']['result'][0]

                # 결과 표시
                parcel_addr = result.get('parcel', '지번 주소 없음')
                road_addr = result.get('road', '도로명 주소 없음')

                result_text = f"지번 주소: {parcel_addr}\n도로명 주소: {road_addr}"
                self.resultLabel.setText(result_text)

                logger.info(f"역지오코딩 성공: {parcel_addr}")
            else:
                error_msg = response.get('response', {}).get('error', {}).get('text', '주소를 찾을 수 없습니다.')
                self.resultLabel.setText(f"오류: {error_msg}")

        except ValueError:
            self.show_error_message("오류", "유효한 좌표를 입력해주세요.")
        except Exception as e:
            logger.error(f"역지오코딩 오류: {e}")
            self.resultLabel.setText(f"오류: {str(e)}")