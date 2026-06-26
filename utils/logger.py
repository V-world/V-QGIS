"""
V-QGIS 통합 로깅.

플러그인의 모든 진단 로그는 QGIS '로그 메시지' 패널의 "V-QGIS" 탭 하나로 모은다.
(보기 ▸ 패널 ▸ 로그 메시지 → "V-QGIS" 탭)
사용자 문의 시 이 탭 내용만 복사해 받으면 되도록 기능별 태그를 통일했다.

동작 방식: 플러그인 패키지 루트 로거에 _QgisLogHandler를 한 번 달아 두면,
각 모듈의 logging.getLogger(__name__) 출력과 아래 log_* 헬퍼가 모두
같은 경로(파이썬 로깅 → 핸들러 → QGIS 패널)로 흐른다. 중복 출력 없음.

패널과 별개로 같은 로그를 파일(datas/logs/v-qgis.log)에도 상시 기록한다.
설정 ▸ 정보 ▸ '로그 파일 저장'으로 사용자가 파일을 내보내 전달할 수 있다.

QgsMessageLog.logMessage는 스레드 안전하므로 워커 스레드에서도 그대로 쓸 수 있다.
"""
import os
import logging
from logging.handlers import RotatingFileHandler

from qgis.core import QgsMessageLog, Qgis

from ..constants import LOG_DIR, LOG_FILE

LOG_TAG = "V-QGIS"

# 플러그인 패키지 루트 (플러그인 폴더명). 모든 하위 모듈 로거가 여기로 전파된다.
_PKG_ROOT = __name__.split('.')[0]

_py_logger = logging.getLogger(f"{_PKG_ROOT}.vqgis")


class _QgisLogHandler(logging.Handler):
    """
    플러그인 모듈들의 logging.getLogger(__name__) 출력을 QGIS 패널 "V-QGIS" 탭으로 전달.
    (모듈마다 로깅 코드를 고치지 않아도 모든 로그가 한 탭에 모인다)
    """

    def emit(self, record):
        try:
            if record.levelno >= logging.ERROR:
                level = Qgis.MessageLevel.Critical
            elif record.levelno >= logging.WARNING:
                level = Qgis.MessageLevel.Warning
            else:
                level = Qgis.MessageLevel.Info
            # 기본 포매터는 logger.exception의 트레이스백도 함께 붙여 준다
            QgsMessageLog.logMessage(self.format(record), LOG_TAG, level)
        except Exception:
            pass


def _install_handler():
    root_logger = logging.getLogger(_PKG_ROOT)
    # 플러그인 재로드 시 핸들러가 중복 등록되지 않도록 방지
    if not any(isinstance(h, _QgisLogHandler) for h in root_logger.handlers):
        root_logger.addHandler(_QgisLogHandler())

    # 파일 상시 기록 (실패해도 패널 로깅은 계속 동작해야 하므로 조용히 건너뜀)
    if not any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            file_handler = RotatingFileHandler(
                LOG_FILE, maxBytes=1024 * 1024, backupCount=2,
                encoding='utf-8', delay=True,
            )
            file_handler.setFormatter(
                logging.Formatter('%(asctime)s %(levelname)s %(message)s')
            )
            root_logger.addHandler(file_handler)
        except Exception:
            pass

    if root_logger.level == logging.NOTSET or root_logger.level > logging.INFO:
        root_logger.setLevel(logging.INFO)


_install_handler()


def export_logs(dest_path: str) -> bool:
    """
    로그 파일(백업 포함, 오래된 순)을 하나로 합쳐 dest_path에 저장.
    저장할 로그가 하나도 없으면 False.
    """
    for handler in logging.getLogger(_PKG_ROOT).handlers:
        try:
            handler.flush()
        except Exception:
            pass

    sources = [
        path for path in (f"{LOG_FILE}.2", f"{LOG_FILE}.1", LOG_FILE)
        if os.path.isfile(path)
    ]
    if not sources:
        return False

    with open(dest_path, 'w', encoding='utf-8') as dest:
        for src in sources:
            try:
                with open(src, 'r', encoding='utf-8', errors='replace') as f:
                    dest.write(f.read())
            except OSError:
                continue
    return True


def log_message(message: str, level=Qgis.MessageLevel.Info):
    """QGIS 로그 메시지 패널("V-QGIS" 탭)에 남긴다."""
    if level == Qgis.MessageLevel.Critical:
        _py_logger.error(message)
    elif level == Qgis.MessageLevel.Warning:
        _py_logger.warning(message)
    else:
        _py_logger.info(message)


def log_info(message: str):
    log_message(message, Qgis.MessageLevel.Info)


def log_warning(message: str):
    log_message(message, Qgis.MessageLevel.Warning)


def log_error(message: str):
    log_message(message, Qgis.MessageLevel.Critical)
