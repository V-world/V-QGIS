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

    @staticmethod
    def read_env(filepath: str) -> Dict[str, str]:
        """
            .env 파일 읽기

            Returns:
                환경 변수 딕셔너리
        """
        env_vars = {}

        if not os.path.exists(filepath):
            return env_vars

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()

                    # 빈 줄이나 주석 무시
                    if not line or line.startswith('#'):
                        continue

                    # KEY=VALUE 형식 파싱
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()

                        # 따옴표 제거
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]

                        env_vars[key] = value

            logger.debug(f".env 파일 로드 완료: {filepath}")
            return env_vars

        except Exception as e:
            logger.error(f".env 파일 읽기 실패 {filepath}: {e}")
            return {}

    @staticmethod
    def write_env(filepath: str, env_vars: Dict[str, str]) -> None:
        """
            .env 파일 쓰기

            Args:
                filepath: 파일 경로
                env_vars: 환경 변수 딕셔너리
        """
        try:
            # 디렉토리 확인
            directory = os.path.dirname(filepath)
            if directory:
                FileManager.ensure_directory(directory)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("# V-World QGIS Plugin Environment Variables\n")
                f.write("# 이 파일은 자동으로 생성되었습니다.\n\n")

                for key, value in env_vars.items():
                    # 값에 공백이 있으면 따옴표로 감싸기
                    if ' ' in value or '#' in value:
                        f.write(f'{key}="{value}"\n')
                    else:
                        f.write(f'{key}={value}\n')

            logger.info(f".env 파일 저장 완료: {filepath}")

        except Exception as e:
            logger.error(f".env 파일 쓰기 실패 {filepath}: {e}")
            raise FileError(f".env 파일 저장 실패: {filepath}")

    @staticmethod
    def update_env_variable(filepath: str, key: str, value: str) -> None:
        """
            .env 파일의 특정 변수 업데이트

            Args:
                filepath: 파일 경로
                key: 환경 변수 키
                value: 환경 변수 값
        """
        env_vars = FileManager.read_env(filepath)
        env_vars[key] = value
        FileManager.write_env(filepath, env_vars)