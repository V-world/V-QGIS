import logging
from typing import Callable, Dict

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QCheckBox,
)
from qgis.core import QgsProject

from .base_widget import BaseDialog
from ..constants import WMTS_LAYER_PREFIX, SEARCH_RESULT_LAYER, SEARCHES_FILE
from ..utils import ConfigManager, FileManager, ThemeColors

logger = logging.getLogger(__name__)


class _StepCard(QFrame):
    """
        시작하기 단계 한 장.
        왼쪽 상태 배지(번호 → 완료 시 ✓) + 제목/설명 + 액션 버튼들.
        '이미 끝낸 단계'와 '지금 할 단계'를 한눈에 구분해 초보자의 길잡이가 된다.
    """

    def __init__(self, number: int, title: str, desc: str, buttons, parent=None):
        super().__init__(parent)
        self.number = number
        self._done = False
        self.setObjectName("stepCard")

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 12, 14, 12)
        row.setSpacing(12)

        # 상태 배지
        self.badge = QLabel(str(number))
        self.badge.setFixedSize(24, 24)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignTop)

        # 본문
        body = QVBoxLayout()
        body.setSpacing(4)
        self.titleLbl = QLabel(title)
        self.titleLbl.setStyleSheet("font-weight: 700; font-size: 11pt;")
        body.addWidget(self.titleLbl)

        self.descLbl = QLabel(desc)
        self.descLbl.setWordWrap(True)
        body.addWidget(self.descLbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.setContentsMargins(0, 6, 0, 0)
        for i, (label, handler) in enumerate(buttons):
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            # 첫 버튼(권장 동작)만 살짝 강조 — 모든 버튼을 primary로 만들지 않는다.
            if i == 0:
                f = btn.font()
                f.setBold(True)
                btn.setFont(f)
            btn.clicked.connect(lambda _checked=False, h=handler: h())
            btn_row.addWidget(btn)
        btn_row.addStretch(1)
        body.addLayout(btn_row)

        row.addLayout(body, 1)
        self.set_done(False)

    def set_done(self, done: bool):
        self._done = done
        brand = ThemeColors.brand()
        muted = ThemeColors.muted()
        if done:
            self.badge.setText("✓")
            self.badge.setStyleSheet(
                f"QLabel {{ background: {brand}; color: #ffffff;"
                " border-radius: 12px; font-weight: 700; }"
            )
            # 완료한 단계는 한 톤 가라앉혀 '지금 할 일'에 시선이 가도록.
            self.descLbl.setStyleSheet(f"color: {muted};")
            self.setStyleSheet(
                "#stepCard { border: 1px solid palette(mid);"
                " border-radius: 8px; background: palette(window); }"
            )
        else:
            self.badge.setText(str(self.number))
            self.badge.setStyleSheet(
                "QLabel { background: palette(mid); color: palette(window-text);"
                " border-radius: 12px; font-weight: 700; }"
            )
            self.descLbl.setStyleSheet(f"color: {muted};")
            self.setStyleSheet(
                "#stepCard { border: 1px solid palette(mid);"
                " border-radius: 8px; background: palette(base); }"
            )


class OnboardingWidget(BaseDialog):
    """
        '브이월드 시작하기' 안내 팝업(비모달 + 항상 위).
        키 발급 → 배경지도 → 주소 검색의 3단계 체크리스트로 첫 성공까지 안내한다.
        키가 없는 상태를 '오류'가 아니라 '여기서 시작'으로 프레이밍한다.

        모달이 아니어야 한다 — 사용자가 버튼으로 QGIS 본화면(지도 추가·검색)을
        조작해야 하므로 비모달로 띄우고, 묻히지 않도록 staysOnTop을 사용한다.
    """

    def __init__(self, callbacks: Dict[str, Callable], parent=None):
        super().__init__(parent)
        self._cb = callbacks
        self.config = ConfigManager()
        self._build_ui()
        self._wire_project_signals()
        self.refresh_status()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        self.setWindowTitle("브이월드 시작하기")
        self.setMinimumSize(440, 540)
        self.resize(460, 560)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(
            self.make_brand_header(
                "브이월드 시작하기", "3단계면 첫 지도를 띄울 수 있어요", ":/icon_base"
            )
        )

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 14, 16, 14)
        body_layout.setSpacing(12)

        intro = QLabel(
            "처음 오셨나요? GIS가 익숙하지 않아도 괜찮습니다. "
            "아래 순서대로 따라 하면 브이월드 지도를 바로 사용할 수 있어요."
        )
        intro.setWordWrap(True)
        body_layout.addWidget(intro)

        self.progressLbl = QLabel()
        self.progressLbl.setStyleSheet("font-weight: 700;")
        body_layout.addWidget(self.progressLbl)

        # 단계 카드
        self.step1 = _StepCard(
            1, "내 인증키 등록하기",
            "기본 지도·검색은 바로 쓸 수 있어요. 엑셀 지오코딩 등 일부 기능은 "
            "본인 무료 인증키가 필요하니 미리 발급·등록해 두면 좋습니다.",
            [
                ("무료 인증키 발급받기", self._on_issue_key),
                ("인증키 입력", self._on_open_settings),
            ],
        )
        body_layout.addWidget(self.step1)

        self.step2 = _StepCard(
            2, "배경지도 띄우기",
            "브이월드 일반지도를 지도 창에 바로 추가합니다. 버튼 한 번이면 됩니다.",
            [("일반지도 추가", self._on_add_basemap)],
        )
        body_layout.addWidget(self.step2)

        self.step3 = _StepCard(
            3, "주소로 이동하기",
            "주소를 검색해 원하는 위치로 지도를 이동해 보세요.",
            [("주소 검색 열기", self._on_open_search)],
        )
        body_layout.addWidget(self.step3)

        # 완료 안내 (모든 단계 완료 시 노출)
        self.doneLbl = QLabel("🎉 준비 완료! 이제 자유롭게 사용해 보세요.")
        self.doneLbl.setWordWrap(True)
        self.doneLbl.setStyleSheet(
            f"color: {ThemeColors.status_info()}; font-weight: 700;"
        )
        self.doneLbl.setVisible(False)
        body_layout.addWidget(self.doneLbl)

        body_layout.addStretch(1)
        outer.addWidget(body)

        # 푸터
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        outer.addWidget(line)

        footer = QWidget()
        footer_row = QHBoxLayout(footer)
        footer_row.setContentsMargins(16, 8, 16, 10)
        self.hideCheck = QCheckBox("다음부터 표시하지 않기")
        self.hideCheck.setChecked(self.config.onboarding_hide)
        self.hideCheck.toggled.connect(self._on_hide_toggled)
        footer_row.addWidget(self.hideCheck)
        footer_row.addStretch(1)
        self.closeBtn = QPushButton("닫기")
        self.closeBtn.clicked.connect(self.close)
        footer_row.addWidget(self.closeBtn)
        outer.addWidget(footer)

    def _wire_project_signals(self):
        """ 레이어 추가/삭제 시 단계 상태 자동 갱신. 닫을 때 해제(닫힌 위젯 접근 방지). """
        self._project_signals = []
        try:
            project = QgsProject.instance()
            for signal in (project.layersAdded, project.layersRemoved):
                signal.connect(self._on_project_changed)
                self._project_signals.append(signal)
        except Exception:
            logger.debug("프로젝트 시그널 연결 실패(무시)")

    def _on_project_changed(self, _layers=None):
        self.refresh_status()

    # ------------------------------------------------------------------
    # 상태 판정
    # ------------------------------------------------------------------
    def _step1_done(self) -> bool:
        # 번들 키가 아니라 '사용자 본인이 등록한 키'를 기준으로 판정.
        # (기본 지도는 번들 키로 동작하지만, 지오코딩 등은 본인 키가 필요)
        try:
            return bool(self.config.user_api_key)
        except Exception:
            return False

    def _step2_done(self) -> bool:
        try:
            for layer in QgsProject.instance().mapLayers().values():
                if layer.name().startswith(WMTS_LAYER_PREFIX):
                    return True
        except Exception:
            pass
        return False

    def _step3_done(self) -> bool:
        # 검색 결과 레이어가 있거나 최근 검색 기록이 있으면 완료로 본다.
        try:
            if QgsProject.instance().mapLayersByName(SEARCH_RESULT_LAYER):
                return True
        except Exception:
            pass
        try:
            return bool(FileManager.read_json(SEARCHES_FILE, {}))
        except Exception:
            return False

    def refresh_status(self):
        """ 세 단계의 완료 상태를 다시 계산해 배지/진행도/완료 안내를 갱신. """
        s1, s2, s3 = self._step1_done(), self._step2_done(), self._step3_done()
        self.step1.set_done(s1)
        self.step2.set_done(s2)
        self.step3.set_done(s3)

        done_count = sum((s1, s2, s3))
        self.progressLbl.setText(f"진행 상황 — {done_count} / 3 단계 완료")
        self.doneLbl.setVisible(done_count == 3)

    # ------------------------------------------------------------------
    # 액션 (메인 플러그인 콜백 호출 후 상태 갱신)
    # ------------------------------------------------------------------
    def _call(self, name: str):
        fn = self._cb.get(name)
        if callable(fn):
            try:
                fn()
            except Exception:
                logger.exception(f"온보딩 콜백 실패: {name}")

    def _on_issue_key(self):
        self._call('issue_key')

    def _on_open_settings(self):
        # 설정은 모달 — 닫힌 뒤 키 입력 결과를 반영.
        self._call('open_settings')
        self.refresh_status()

    def _on_add_basemap(self):
        self._call('add_basemap')
        self.refresh_status()

    def _on_open_search(self):
        self._call('open_search')
        self.refresh_status()

    def _on_hide_toggled(self, checked: bool):
        self.config.onboarding_hide = checked

    def showEvent(self, event):
        # 닫았다가 다시 열 때(시그널이 해제된 상태) 라이브 갱신을 재연결.
        if not getattr(self, '_project_signals', None):
            self._wire_project_signals()
        self.refresh_status()
        super().showEvent(event)

    def closeEvent(self, event):
        # 닫힌 뒤 레이어 변경 시 삭제된 위젯에 접근하지 않도록 시그널 해제.
        for signal in getattr(self, '_project_signals', []):
            try:
                signal.disconnect(self._on_project_changed)
            except (TypeError, RuntimeError):
                pass
        self._project_signals = []
        super().closeEvent(event)
