from functools import wraps
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMessageBox
import logging

from ..config import API_KEY
from .config_manager import ConfigManager

logger = logging.getLogger(__name__)


def with_error_handling(error_message: str = "오류가 발생했습니다"):
    """
        에러 처리 데코레이터
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.exception(f"{func.__name__}에서 오류 발생: {e}")

                # self가 있는 경우 (메서드)
                if args and hasattr(args[0], 'show_error_message'):
                    args[0].show_error_message("오류", f"{error_message}\n\n상세: {str(e)}")
                else:
                    # 전역 메시지 박스
                    QMessageBox.critical(None, "오류", f"{error_message}\n\n상세: {str(e)}")

                return None

        return wrapper

    return decorator


def with_loading_cursor(func):
    """
        로딩 커서 데코레이터
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        QApplication.setOverrideCursor(Qt.WaitCursor)
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