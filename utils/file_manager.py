import os
import json
from typing import Any, Dict, Optional
import logging

from ..exceptions import FileError

logger = logging.getLogger(__name__)


class FileManager:

    @staticmethod
    def ensure_directory(directory: str) -> None:
        """
            디렉토리 생성 확인
        """
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
                logger.info(f"디렉토리 생성: {directory}")
            except Exception as e:
                logger.error(f"디렉토리 생성 실패 {directory}: {e}")
                raise FileError(f"디렉토리 생성 실패: {directory}")

    @staticmethod
    def read_json(filepath: str, default: Any = None) -> Any:
        """
            JSON 파일 읽기
        """
        if not os.path.exists(filepath):
            return default

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"JSON 파일 읽기 실패 {filepath}: {e}")
            return default

    @staticmethod
    def write_json(filepath: str, data: Any) -> None:
        """
            JSON 파일 쓰기
        """
        try:
            # 디렉토리 확인
            directory = os.path.dirname(filepath)
            if directory:
                FileManager.ensure_directory(directory)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"JSON 파일 저장 완료: {filepath}")

        except Exception as e:
            logger.error(f"JSON 파일 쓰기 실패 {filepath}: {e}")
            raise FileError(f"JSON 파일 저장 실패: {filepath}")

    @staticmethod
    def read_text(filepath: str, encoding: str = 'utf-8') -> Optional[str]:
        """
            텍스트 파일 읽기
        """
        if not os.path.exists(filepath):
            return None

        try:
            with open(filepath, 'r', encoding=encoding) as f:
                return f.read()
        except Exception as e:
            logger.error(f"텍스트 파일 읽기 실패 {filepath}: {e}")
            return None

    @staticmethod
    def write_text(filepath: str, content: str, encoding: str = 'utf-8') -> None:
        """
            텍스트 파일 쓰기
        """
        try:
            # 디렉토리 확인
            directory = os.path.dirname(filepath)
            if directory:
                FileManager.ensure_directory(directory)

            with open(filepath, 'w', encoding=encoding) as f:
                f.write(content)

            logger.info(f"텍스트 파일 저장 완료: {filepath}")

        except Exception as e:
            logger.error(f"텍스트 파일 쓰기 실패 {filepath}: {e}")
            raise FileError(f"텍스트 파일 저장 실패: {filepath}")

    @staticmethod
    def delete_file(filepath: str) -> bool:
        """
            파일 삭제
        """
        if not os.path.exists(filepath):
            return True

        try:
            os.remove(filepath)
            logger.info(f"파일 삭제: {filepath}")
            return True
        except Exception as e:
            logger.error(f"파일 삭제 실패 {filepath}: {e}")
            return False