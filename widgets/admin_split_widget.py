import logging

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QRadioButton, QButtonGroup, QComboBox, QPushButton, QToolButton,
    QProgressBar, QGroupBox, QFormLayout, QAbstractItemView,
)
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsRectangle,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform,
)

from .base_widget import BaseWidget
from ..constants import ERROR_MESSAGES, ADMIN_SIDO
from ..core import AdminSplitWorker, AdminUnitsWorker

logger = logging.getLogger(__name__)

# 분할 단위 식별자
LEVEL_SIDO = 'sido'
LEVEL_SIGUNGU = 'sigungu'
LEVEL_EMD = 'emd'


class AdminSplitWidget(BaseWidget):
    """
        행정구역 단위 데이터 분할 도크.
        - 대상 레이어를 광역시도 / 시군구 / 읍면동 단위로 잘라 단위별 레이어 묶음 생성.
        - 시군구 분할은 광역시도 1곳, 읍면동 분할은 광역시도+시군구 선택을 요구한다.
        - 경계 폴리곤은 브이월드 WFS에서 실시간 조회(백그라운드), 결과는 메모리 레이어 그룹으로 추가.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.split_worker = None
        self.units_worker = None
        self._setup_ui()
        self._connect_signals()
        self.refresh_layer_list()
        self._on_level_changed()

    # ------------------------------------------------------------------
    # UI 구성
    # ------------------------------------------------------------------
    def _setup_ui(self):
        self.setWindowTitle("행정구역 분할")

        contents = QWidget()
        contents.setObjectName("dockWidgetContents")
        outer = QVBoxLayout(contents)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(
            self.make_brand_header(
                "행정구역 분할",
                "데이터를 시도·시군구·읍면동 단위로 나눕니다",
                ":/icon_layer",
            )
        )

        body = QVBoxLayout()
        body.setContentsMargins(16, 12, 16, 12)
        body.setSpacing(10)

        # 1) 대상 레이어
        body.addWidget(self.make_section_caption("1. 대상 레이어"))

        layer_row = QHBoxLayout()
        layer_row.setSpacing(8)
        hint1 = QLabel("나눌 레이어를 하나 선택하세요.")
        layer_row.addWidget(hint1)
        layer_row.addStretch(1)
        self.refreshBtn = QToolButton()
        self.refreshBtn.setText("새로고침")
        self.refreshBtn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.refreshBtn.setToolTip("현재 프로젝트의 벡터 레이어를 다시 불러옵니다.")
        layer_row.addWidget(self.refreshBtn)
        body.addLayout(layer_row)

        self.layersList = QListWidget()
        self.layersList.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.layersList.setMaximumHeight(150)
        body.addWidget(self.layersList)

        # 2) 분할 단위
        body.addWidget(self.make_section_caption("2. 분할 단위"))
        level_row = QHBoxLayout()
        level_row.setSpacing(12)
        self.radioSido = QRadioButton("광역시도")
        self.radioSigungu = QRadioButton("시군구")
        self.radioEmd = QRadioButton("읍면동")
        self.radioSido.setChecked(True)
        self.levelGroup = QButtonGroup(self)
        for i, radio in enumerate(
            (self.radioSido, self.radioSigungu, self.radioEmd)
        ):
            self.levelGroup.addButton(radio, i)
            level_row.addWidget(radio)
        level_row.addStretch(1)
        body.addLayout(level_row)

        # 3) 범위 제한 (시군구/읍면동에서만 표시)
        self.restrictBox = QGroupBox("3. 범위 제한")
        form = QFormLayout(self.restrictBox)
        form.setContentsMargins(12, 10, 12, 10)
        form.setSpacing(8)

        self.sidoCombo = QComboBox()
        for name, prefixes in ADMIN_SIDO:
            self.sidoCombo.addItem(name, prefixes)
        self.sidoLabel = QLabel("광역시도:")
        form.addRow(self.sidoLabel, self.sidoCombo)

        self.sigunguCombo = QComboBox()
        self.sigunguLabel = QLabel("시군구:")
        form.addRow(self.sigunguLabel, self.sigunguCombo)
        body.addWidget(self.restrictBox)

        # 실행 버튼
        self.splitBtn = QPushButton("분할하기")
        self.splitBtn.setMinimumHeight(34)
        body.addWidget(self.splitBtn)

        # 진행률 + 상태
        self.progressBar = QProgressBar()
        self.progressBar.setVisible(False)
        body.addWidget(self.progressBar)

        self.statusLabel = QLabel("")
        self.statusLabel.setWordWrap(True)
        body.addWidget(self.statusLabel)

        body.addStretch(1)
        outer.addLayout(body)
        self.setWidget(contents)

    def _connect_signals(self):
        self.refreshBtn.clicked.connect(self.refresh_layer_list)
        self.splitBtn.clicked.connect(self._on_split)
        self.radioSido.toggled.connect(lambda _c=False: self._on_level_changed())
        self.radioSigungu.toggled.connect(lambda _c=False: self._on_level_changed())
        self.radioEmd.toggled.connect(lambda _c=False: self._on_level_changed())
        self.sidoCombo.currentIndexChanged.connect(self._on_sido_changed)
        self.layersList.itemSelectionChanged.connect(self._on_target_changed)

    # ------------------------------------------------------------------
    # 레이어 목록
    # ------------------------------------------------------------------
    def refresh_layer_list(self):
        """프로젝트의 (지오메트리가 있는) 벡터 레이어를 목록에 채운다."""
        prev_id = None
        sel = self.layersList.selectedItems()
        if sel:
            prev_id = sel[0].data(Qt.ItemDataRole.UserRole)

        self.layersList.clear()

        spatial_layers = [
            lyr for lyr in QgsProject.instance().mapLayers().values()
            if isinstance(lyr, QgsVectorLayer) and lyr.isSpatial()
        ]

        if not spatial_layers:
            self._set_list_placeholder(
                self.layersList, "프로젝트에 분할할 벡터 레이어가 없습니다."
            )
            return

        for lyr in spatial_layers:
            item = QListWidgetItem(lyr.name())
            item.setData(Qt.ItemDataRole.UserRole, lyr.id())
            item.setToolTip(f"레이어: {lyr.name()}\n소스: {lyr.source()}")
            if lyr.id() == prev_id:
                item.setSelected(True)
            self.layersList.addItem(item)

    def _selected_target_layer(self):
        items = self.layersList.selectedItems()
        if not items:
            return None
        layer_id = items[0].data(Qt.ItemDataRole.UserRole)
        if not layer_id:
            return None
        return QgsProject.instance().mapLayer(layer_id)

    # ------------------------------------------------------------------
    # 단위/범위 인터랙션
    # ------------------------------------------------------------------
    def _current_level(self) -> str:
        if self.radioSigungu.isChecked():
            return LEVEL_SIGUNGU
        if self.radioEmd.isChecked():
            return LEVEL_EMD
        return LEVEL_SIDO

    def _on_level_changed(self):
        """분할 단위에 따라 범위 제한(시도/시군구) 위젯 표시를 전환."""
        level = self._current_level()
        show_sido = level in (LEVEL_SIGUNGU, LEVEL_EMD)
        show_sigungu = level == LEVEL_EMD

        self.restrictBox.setVisible(show_sido)
        self.sidoLabel.setVisible(show_sido)
        self.sidoCombo.setVisible(show_sido)
        self.sigunguLabel.setVisible(show_sigungu)
        self.sigunguCombo.setVisible(show_sigungu)

        # 읍면동 모드로 들어오면 현재 시도의 시군구 목록을 불러온다.
        if level == LEVEL_EMD:
            self._load_sigungu_list()

    def _on_sido_changed(self, _index=0):
        if self._current_level() == LEVEL_EMD:
            self._load_sigungu_list()

    def _on_target_changed(self):
        # 대상 레이어가 바뀌면(읍면동 모드) 그 데이터 범위로 시군구 목록을 다시 불러온다.
        if self._current_level() == LEVEL_EMD:
            self._load_sigungu_list()

    def _target_extent_4326(self, target) -> QgsRectangle:
        """대상 레이어의 데이터 범위를 EPSG:4326 bbox로 반환."""
        ext = target.extent()
        crs = target.crs()
        if crs.isValid() and crs.authid() != "EPSG:4326":
            xform = QgsCoordinateTransform(
                crs, QgsCoordinateReferenceSystem("EPSG:4326"),
                QgsProject.instance().transformContext(),
            )
            ext = xform.transformBoundingBox(ext)
        return ext

    def _load_sigungu_list(self):
        """대상 데이터 범위 안에서 선택한 시도의 시군구 목록을 조회해 콤보를 채운다."""
        if self.units_worker is not None and self.units_worker.isRunning():
            return

        prefixes = self.sidoCombo.currentData()
        target = self._selected_target_layer()
        if not prefixes:
            return

        self.sigunguCombo.clear()
        if target is None:
            self.sigunguCombo.addItem("대상 레이어를 먼저 선택하세요", None)
            self.sigunguCombo.setEnabled(False)
            return

        self.sigunguCombo.addItem("불러오는 중...", None)
        self.sigunguCombo.setEnabled(False)
        self.splitBtn.setEnabled(False)

        self.units_worker = AdminUnitsWorker(
            LEVEL_SIGUNGU, prefixes=prefixes,
            rect=self._target_extent_4326(target),
        )
        self.units_worker.finished.connect(self._on_units_loaded)
        self.units_worker.warning.connect(
            lambda msg: self.show_warning_message("행정구역 분할", msg)
        )
        self.units_worker.error.connect(self._on_units_error)
        self.units_worker.start()

    def _on_units_loaded(self, units: list):
        self.sigunguCombo.clear()
        self.sigunguCombo.setEnabled(True)
        self.splitBtn.setEnabled(True)
        if not units:
            self.sigunguCombo.addItem("이 데이터 범위에 시군구가 없습니다", None)
        else:
            for u in units:
                self.sigunguCombo.addItem(u['name'], {'code': u['code']})

    def _on_units_error(self, message: str):
        self.sigunguCombo.clear()
        self.sigunguCombo.setEnabled(True)
        self.splitBtn.setEnabled(True)
        self.sigunguCombo.addItem("불러오기 실패", None)
        self.show_error_message(
            "행정구역 분할",
            f"{ERROR_MESSAGES['admin_wfs_failed']}\n(상세: {message})",
        )
        logger.error(f"시군구 목록 조회 실패: {message}")

    # ------------------------------------------------------------------
    # 분할 실행
    # ------------------------------------------------------------------
    def _on_split(self, _checked=False):
        target = self._selected_target_layer()
        if target is None:
            self.show_warning_message("행정구역 분할", ERROR_MESSAGES['no_target_layer'])
            return

        level = self._current_level()
        # 조회 범위 = 대상 데이터의 실제 범위(EPSG:4326). 데이터가 있는 곳의 행정구역만 받는다.
        rect = self._target_extent_4326(target)
        prefixes = None
        group_name = ""

        if level == LEVEL_SIDO:
            group_name = "광역시도 분할"

        elif level == LEVEL_SIGUNGU:
            prefixes = self.sidoCombo.currentData()
            if not prefixes:
                self.show_warning_message("행정구역 분할", ERROR_MESSAGES['sido_required'])
                return
            group_name = f"{self.sidoCombo.currentText()} · 시군구 분할"

        else:  # LEVEL_EMD
            sido_prefixes = self.sidoCombo.currentData()
            sigungu_data = self.sigunguCombo.currentData()
            if not sido_prefixes:
                self.show_warning_message("행정구역 분할", ERROR_MESSAGES['sido_required'])
                return
            if not sigungu_data:
                self.show_warning_message("행정구역 분할", ERROR_MESSAGES['sigungu_required'])
                return
            prefixes = (sigungu_data['code'],)
            group_name = f"{self.sigunguCombo.currentText()} · 읍면동 분할"

        self._pending_group_name = group_name
        self._last_target = target
        self._start_split(target, level, prefixes, rect)

    def _start_split(self, target, level, prefixes, rect):
        self.progressBar.setVisible(True)
        self.progressBar.setRange(0, 0)  # 경계 조회 동안 불확정 모드
        self.statusLabel.setText("행정구역 경계를 불러오는 중...")
        self.splitBtn.setEnabled(False)

        self.split_worker = AdminSplitWorker(target, level, prefixes, rect)
        self.split_worker.status.connect(self.statusLabel.setText)
        self.split_worker.progress.connect(self._on_split_progress)
        self.split_worker.finished.connect(self._on_split_finished)
        self.split_worker.warning.connect(
            lambda msg: self.show_warning_message("행정구역 분할", msg)
        )
        self.split_worker.error.connect(self._on_split_error)
        self.split_worker.start()

    def _on_split_progress(self, done: int, total: int):
        if total > 0:
            self.progressBar.setRange(0, total)
            self.progressBar.setValue(done)

    def _on_split_finished(self, results: list):
        self.progressBar.setVisible(False)
        self.statusLabel.setText("")
        self.splitBtn.setEnabled(True)

        if not results:
            tgt = getattr(self, '_last_target', None)
            detail = ""
            if tgt is not None:
                detail = (
                    f"\n(경계는 정상적으로 불러왔습니다. 다만 대상 "
                    f"'{tgt.name()}'[{tgt.crs().authid()}, {tgt.featureCount()}개]의 "
                    f"데이터가 그 경계 안에 들어가지 않습니다. 대상 레이어의 좌표계가 "
                    f"올바른지 확인해 주세요.)"
                )
            self.show_warning_message(
                "행정구역 분할", ERROR_MESSAGES['split_no_result'] + detail
            )
            return

        group_name = getattr(self, '_pending_group_name', "행정구역 분할")
        project = QgsProject.instance()
        root = project.layerTreeRoot()
        group = root.insertGroup(0, group_name)
        for name, layer in results:
            layer.setName(name)
            project.addMapLayer(layer, False)
            group.addLayer(layer)

        self.show_success_message(
            "행정구역 분할",
            f"'{group_name}' 그룹에 {len(results)}개 구역 레이어를 만들었습니다.",
        )
        logger.info(f"행정구역 분할 완료: {group_name}, {len(results)}개")

    def _on_split_error(self, message: str):
        self.progressBar.setVisible(False)
        self.statusLabel.setText("")
        self.splitBtn.setEnabled(True)
        self.show_error_message(
            "행정구역 분할",
            f"{ERROR_MESSAGES['admin_wfs_failed']}\n(상세: {message})",
        )
        logger.error(f"행정구역 분할 실패: {message}")

    # ------------------------------------------------------------------
    def closeEvent(self, event):
        for worker in (self.split_worker, self.units_worker):
            try:
                if worker is not None and worker.isRunning():
                    if hasattr(worker, 'cancel'):
                        worker.cancel()
                    worker.quit()
                    worker.wait(2000)
            except Exception:
                pass
        super().closeEvent(event)
