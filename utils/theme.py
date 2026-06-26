from qgis.PyQt.QtGui import QPalette
from qgis.PyQt.QtWidgets import QApplication


def is_dark_theme() -> bool:
    """
        QGIS(또는 OS) 팔레트 기반 다크 테마 감지.
        Window 배경 명도(lightness)가 절반 미만이면 다크로 판정.
    """
    pal = QApplication.palette()
    bg = pal.color(QPalette.ColorRole.Window)
    return bg.lightness() < 128


class ThemeColors:
    """
        다크/라이트 테마 양쪽에서 잘 보이는 텍스트 색상 모음.
        라이트 = 진한 채도, 다크 = 한 단계 밝은 톤.
    """

    @classmethod
    def muted(cls) -> str:
        """ 부가 설명/캡션용 흐린 텍스트 """
        return "#b0b3b8" if is_dark_theme() else "#666666"

    @classmethod
    def brand(cls) -> str:
        """ 브이월드 브랜드 강조색 (헤더 스트립/주요 강조). """
        # 다크 테마는 흰색 텍스트 대비(AA)를 위해 한 단계 진한 블루 사용.
        return "#1d4ed8" if is_dark_theme() else "#0b5fa5"

    @classmethod
    def on_brand(cls) -> str:
        """ 브랜드색 배경 위의 텍스트 색. """
        return "#ffffff"

    @classmethod
    def link(cls) -> str:
        """ 하이퍼링크 """
        return "#7aa7ff" if is_dark_theme() else "#0000ff"

    @classmethod
    def warning(cls) -> str:
        """ 본문 내 경고/강조 텍스트 (빨강) """
        return "#ff7a85" if is_dark_theme() else "#ff0004"

    @classmethod
    def status_info(cls) -> str:
        return "#7fd391" if is_dark_theme() else "#2e7d32"

    @classmethod
    def status_warn(cls) -> str:
        return "#ffb74d" if is_dark_theme() else "#ef6c00"

    @classmethod
    def status_error(cls) -> str:
        return "#ef9a9a" if is_dark_theme() else "#c62828"
