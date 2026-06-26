from functools import wraps
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QApplication, QMessageBox
import logging

from ..config import API_KEY
from ..constants import ERROR_MESSAGES
from ..exceptions import VWorldError
from .config_manager import ConfigManager

logger = logging.getLogger(__name__)


def _report_error(args, message: str):
    """
        에러를 위젯의 show_error_message로 전달, 없으면 통합 알림으로 폴백.
    """
    if args and hasattr(args[0], 'show_error_message'):
        args[0].show_error_message("오류", message)
    else:
        from . import feedback
        feedback.notify_error("오류", message)


def with_error_handling(error_message: str = "오류가 발생했습니다"):
    """
        에러 처리 데코레이터
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except VWorldError as e:
                # 플러그인이 직접 던진 예외 - 메시지가 사용자용으로 다듬어져 있음
                logger.warning(f"{func.__name__} - {type(e).__name__}: {e}")
                _report_error(args, str(e) or error_message)
            except Exception:
                # 예상치 못한 오류 - 상세 내용은 로그에만 남기고 사용자에게는 친절한 안내
                logger.exception(f"{func.__name__}에서 예상치 못한 오류 발생")
                _report_error(args, error_message)

            return None

        return wrapper

    return decorator


def with_loading_cursor(func):
    """
        로딩 커서 데코레이터
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            return func(*args, **kwargs)
        finally:
            QApplication.restoreOverrideCursor()

    return wrapper


def require_api_key(func):
    """
        API 키 필수 데코레이터
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        # config.py의 API_KEY 우선 확인
        if API_KEY:
            return func(*args, **kwargs)

        # ConfigManager에서 확인
        config = ConfigManager()
        if not config.api_key:
            # self가 있는 경우 (메서드)
            if args and hasattr(args[0], 'show_error_message'):
                args[0].show_error_message("API 키 필요", "API 키가 설정되지 않았습니다.\n설정에서 API 키를 입력해주세요.")
            else:
                QMessageBox.warning(None, "API 키 필요", "API 키가 설정되지 않았습니다.\n설정에서 API 키를 입력해주세요.")
            return None

        return func(*args, **kwargs)

    return wrapper


def require_user_api_key(func):
    """
        사용자 본인 API 키 필수 데코레이터.
        config.py의 키는 무시하고 옵션 창에 저장된 사용자 키만 검사.
        엑셀 지오코딩 등 사용자 쿼터로 동작해야 하는 기능에 사용.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        config = ConfigManager()
        if not config.user_api_key:
            msg = ERROR_MESSAGES['user_api_key_missing']
            if args and hasattr(args[0], 'show_warning_message'):
                args[0].show_warning_message("사용자 API 키 필요", msg)
            elif args and hasattr(args[0], 'show_error_message'):
                args[0].show_error_message("사용자 API 키 필요", msg)
            else:
                QMessageBox.warning(None, "사용자 API 키 필요", msg)
            return None
        return func(*args, **kwargs)

    return wrapper