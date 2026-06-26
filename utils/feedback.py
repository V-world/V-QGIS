"""
    통합 사용자 알림 (Unified user feedback).

    표시 정책 (사용자 요청에 따라 변경):
    - 정보(info): 캔버스 메시지 바를 쓰지 않고 로그에만 남긴다(비방해).
    - 성공(success): 기본은 무음(로그만). 사용자가 설정에서 '작업 완료 팝업'을
      켠 경우에만 차단 팝업으로 표시(opt-in).
    - 경고/오류(warning/error): 캔버스 메시지 바 대신 팝업으로 표시(확실히 인지).
    - 예/아니오 결정(ask): 차단 모달 유지.
"""
import logging

from qgis.PyQt import QtWidgets

logger = logging.getLogger(__name__)


def notify_info(title: str, message: str, parent=None):
    """
        정보 알림 - 캔버스 메시지 바를 쓰지 않고 로그에만 남긴다.
        (작업 진행 등 가벼운 안내가 지도 위에 계속 떠 방해되지 않도록)
    """
    logger.info(f"{title}: {message}" if title else message)


def notify_warning(title: str, message: str, parent=None):
    """ 경고 알림 - 캔버스 메시지 바 대신 팝업으로 표시. """
    logger.warning(f"{title}: {message}" if title else message)
    QtWidgets.QMessageBox.warning(parent, title, message)


def notify_error(title: str, message: str, parent=None):
    """ 에러 알림 - 캔버스 메시지 바 대신 팝업으로 표시. """
    logger.error(f"{title}: {message}" if title else message)
    QtWidgets.QMessageBox.critical(parent, title, message)


def notify_success(title: str, message: str, parent=None):
    """
        성공 알림. 기본은 무음(로그만)으로 처리해 캔버스를 방해하지 않는다.
        사용자가 설정에서 '작업 완료 팝업'을 켠 경우에만 차단 팝업으로 표시.
    """
    try:
        from .config_manager import ConfigManager
        show_popup = ConfigManager().show_success_popup
    except Exception:
        show_popup = False

    logger.info(f"{title}: {message}" if title else message)

    if show_popup:
        QtWidgets.QMessageBox.information(parent, title, message)


def ask(parent, title: str, message: str) -> bool:
    """
        예/아니오 결정 - 사용자 결정이 필요하므로 '차단' 모달을 유지한다.
    """
    reply = QtWidgets.QMessageBox.question(
        parent, title, message,
        QtWidgets.QMessageBox.StandardButton.Yes
        | QtWidgets.QMessageBox.StandardButton.No,
        QtWidgets.QMessageBox.StandardButton.No,
    )
    return reply == QtWidgets.QMessageBox.StandardButton.Yes
