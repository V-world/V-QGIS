import json

from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import (
    QPushButton, QLabel, QLineEdit, QVBoxLayout, QHBoxLayout,
    QGroupBox, QApplication,
)
from qgis.core import (
    QgsPointXY, QgsCoordinateTransform, QgsCoordinateReferenceSystem,
    QgsProject,
)
from qgis.gui import QgsMapToolEmitPoint

from .base_widget import BaseDialog
from ..utils import (
    ApiClient, with_error_handling, require_api_key,
    log_info, log_warning, log_error,
)


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


class ReverseGeocodingWidget(BaseDialog):
    """
        역지오코딩 위젯 (지도 클릭으로 주소 조회).
        전용 .ui는 현재 레이아웃과 위젯 구성이 달라 사용하지 않고 코드에서 동적 구성.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

        self.api_client = ApiClient()
        self.point_tool = None
        self._connect_signals()

    def _setup_ui(self):
        """
            UI 동적 생성 (UI 파일이 없는 경우)
        """
        self.setWindowTitle("주소 조회")
        self.resize(480, 220)

        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(
            self.make_brand_header(
                "주소 조회", "지도를 클릭해 도로명·지번 주소 확인", ":/icon_rgc"
            )
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # 지도 선택 버튼
        self.spotClick = QPushButton("지도에서 선택")
        layout.addWidget(self.spotClick)

        # 결과 그룹
        result_group = QGroupBox("조회 결과")
        result_layout = QVBoxLayout()

        # 안내 라벨 (초기/오류 메시지용)
        self.hintLabel = QLabel("'지도에서 선택' 버튼을 누르고 지도를 클릭하세요.")
        self.hintLabel.setWordWrap(True)
        result_layout.addWidget(self.hintLabel)

        # 도로명 주소 행
        road_row = QHBoxLayout()
        road_label = QLabel("도로명")
        road_label.setMinimumWidth(56)
        self.roadAddrEdit = QLineEdit()
        self.roadAddrEdit.setReadOnly(True)
        self.roadAddrEdit.setPlaceholderText("도로명 주소가 여기에 표시됩니다.")
        self.copyRoadBtn = QPushButton("복사")
        self.copyRoadBtn.setEnabled(False)
        self.copyRoadBtn.setMinimumWidth(60)
        road_row.addWidget(road_label)
        road_row.addWidget(self.roadAddrEdit, 1)
        road_row.addWidget(self.copyRoadBtn)
        result_layout.addLayout(road_row)

        # 지번 주소 행
        parcel_row = QHBoxLayout()
        parcel_label = QLabel("지번")
        parcel_label.setMinimumWidth(56)
        self.parcelAddrEdit = QLineEdit()
        self.parcelAddrEdit.setReadOnly(True)
        self.parcelAddrEdit.setPlaceholderText("지번 주소가 여기에 표시됩니다.")
        self.copyParcelBtn = QPushButton("복사")
        self.copyParcelBtn.setEnabled(False)
        self.copyParcelBtn.setMinimumWidth(60)
        parcel_row.addWidget(parcel_label)
        parcel_row.addWidget(self.parcelAddrEdit, 1)
        parcel_row.addWidget(self.copyParcelBtn)
        result_layout.addLayout(parcel_row)

        result_group.setLayout(result_layout)
        layout.addWidget(result_group)

        outer.addLayout(layout)
        self.setLayout(outer)

        # 하위 호환: 기존 resultLabel 참조가 있을 경우를 대비
        self.resultLabel = self.hintLabel

    def _connect_signals(self):
        """
            시그널 연결
        """
        if hasattr(self, 'spotClick'):
            self.spotClick.clicked.connect(self.on_spot_clicked)
        if hasattr(self, 'copyRoadBtn'):
            self.copyRoadBtn.clicked.connect(
                lambda _checked=False: self._copy_address(self.roadAddrEdit, self.copyRoadBtn)
            )
        if hasattr(self, 'copyParcelBtn'):
            self.copyParcelBtn.clicked.connect(
                lambda _checked=False: self._copy_address(self.parcelAddrEdit, self.copyParcelBtn)
            )

    def _copy_address(self, line_edit: QLineEdit, button: QPushButton):
        """
            QLineEdit의 주소를 클립보드로 복사하고 버튼 라벨로 짧은 피드백.
        """
        text = line_edit.text().strip()
        if not text:
            return
        QApplication.clipboard().setText(text)
        orig_label = '복사'
        button.setText('복사됨!')
        QTimer.singleShot(1500, lambda b=button, l=orig_label: b.setText(l))
        log_info(f"클립보드 복사: {text}")

    def _set_address_field(self, line_edit: QLineEdit, button: QPushButton, value: str):
        """
            주소 필드와 복사 버튼 활성 상태를 함께 갱신.
            value가 비어 있으면 필드 클리어 + 버튼 비활성화.
        """
        line_edit.setText(value or '')
        button.setEnabled(bool(value))

    def on_spot_clicked(self, checked=False):
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
            지도 클릭 시 처리: 좌표 변환 후 역지오코딩 수행
        """
        if button != Qt.MouseButton.LeftButton:
            return

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

        # 위젯 다시 표시 및 기본 맵 도구 복원
        self.show()
        self.canvas.unsetMapTool(self.point_tool)

        # 역지오코딩 수행
        self._lookup_address(point.x(), point.y(), "EPSG:4326")

    @with_error_handling("역지오코딩 중 오류가 발생했습니다")
    @require_api_key
    def _lookup_address(self, x: float, y: float, crs: str):
        """
            V-World 역지오코딩 호출 및 결과 표시
        """
        try:
            log_info(f"역지오코딩 요청: x={x}, y={y}, crs={crs}")

            response = self.api_client.reverse_geocode(x, y, crs)

            try:
                response_dump = json.dumps(response, ensure_ascii=False)
            except Exception:
                response_dump = str(response)
            log_info(f"역지오코딩 응답: {response_dump}")

            resp = response.get('response', {}) if isinstance(response, dict) else {}
            status = resp.get('status')

            if status != 'OK':
                error_msg = (
                    resp.get('error', {}).get('text')
                    or resp.get('status')
                    or '주소를 찾을 수 없습니다.'
                )
                log_warning(f"역지오코딩 실패: status={status}, error={error_msg}")
                self._clear_result(f"오류: {error_msg}")
                return

            # V-World result: type='parcel'/'road' 항목을 가진 리스트 또는 dict
            result_field = resp.get('result', [])
            if isinstance(result_field, dict):
                items = [result_field]
            elif isinstance(result_field, list):
                items = result_field
            else:
                items = []

            log_info(f"역지오코딩 result 항목 수: {len(items)}")

            parcel_addr = None
            road_addr = None
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    log_warning(f"역지오코딩 항목 {idx} 형식이 dict가 아님: {type(item).__name__}")
                    continue
                item_type = item.get('type')
                text = item.get('text')
                if not text:
                    structure = item.get('structure', {}) or {}
                    text = ' '.join(
                        str(structure.get(k, '')).strip()
                        for k in (
                            'level1', 'level2', 'level3',
                            'level4L', 'level4LC', 'level4A', 'level4AC',
                            'level5', 'detail',
                        )
                        if structure.get(k)
                    ).strip() or None

                log_info(f"역지오코딩 항목 {idx}: type={item_type}, text={text}")

                if item_type == 'parcel' and not parcel_addr:
                    parcel_addr = text
                elif item_type == 'road' and not road_addr:
                    road_addr = text

            if not parcel_addr and not road_addr:
                log_warning("역지오코딩: 지번/도로명 주소를 모두 추출하지 못했습니다.")

            self._apply_result(road_addr, parcel_addr)

            log_info(
                f"역지오코딩 성공: road={road_addr or '(없음)'}, parcel={parcel_addr or '(없음)'}"
            )

        except Exception as e:
            log_error(f"역지오코딩 예외: {type(e).__name__}: {e}")
            self._clear_result("주소를 조회하지 못했습니다. 잠시 후 다시 시도해 주세요.")

    def _apply_result(self, road_addr, parcel_addr):
        """
            역지오코딩 결과를 두 입력 필드에 반영하고 안내 라벨 갱신.
        """
        if hasattr(self, 'roadAddrEdit') and hasattr(self, 'parcelAddrEdit'):
            self._set_address_field(self.roadAddrEdit, self.copyRoadBtn, road_addr)
            self._set_address_field(self.parcelAddrEdit, self.copyParcelBtn, parcel_addr)
        if hasattr(self, 'hintLabel'):
            if not road_addr and not parcel_addr:
                self.hintLabel.setText("주소를 찾을 수 없습니다.")
            else:
                self.hintLabel.setText("복사 버튼을 누르거나 필드를 선택해 복사할 수 있습니다.")

    def _clear_result(self, message: str):
        """
            오류 또는 무결과 시 결과 초기화 + 안내 라벨에 메시지 표시.
        """
        if hasattr(self, 'roadAddrEdit') and hasattr(self, 'parcelAddrEdit'):
            self._set_address_field(self.roadAddrEdit, self.copyRoadBtn, '')
            self._set_address_field(self.parcelAddrEdit, self.copyParcelBtn, '')
        if hasattr(self, 'hintLabel'):
            self.hintLabel.setText(message)
