from typing import Dict, Any, Optional
import time
import pickle
import os
import hashlib
import logging

from ..constants import DATA_DIR

logger = logging.getLogger(__name__)


class CacheManager:

    def __init__(self, cache_dir: Optional[str] = None, ttl: int = 3600):
        """
            cache_dir: 캐시 디렉토리 경로
            ttl: Time To Live (초 단위)
        """
        self.cache_dir = cache_dir or os.path.join(DATA_DIR, 'cache')
        self.ttl = ttl
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

        # 캐시 디렉토리 생성
        os.makedirs(self.cache_dir, exist_ok=True)

        # 시작 시 오래된 캐시 정리
        self._cleanup_old_cache()

    def _get_cache_key(self, key: str) -> str:
        """
            캐시 키 생성 (해시 사용)
        """
        return hashlib.md5(key.encode()).hexdigest()

    def _get_cache_filepath(self, key: str) -> str:
        """
            캐시 파일 경로 생성
        """
        cache_key = self._get_cache_key(key)
        return os.path.join(self.cache_dir, f"{cache_key}.cache")

    def get(self, key: str) -> Optional[Any]:
        """
            캐시에서 값 가져오기
        """
        # 메모리 캐시 확인
        if key in self._memory_cache:
            data = self._memory_cache[key]
            if time.time() - data['timestamp'] <= self.ttl:
                logger.debug(f"메모리 캐시 히트: {key}")
                return data['value']
            else:
                del self._memory_cache[key]

        # 파일 캐시 확인
        filepath = self._get_cache_filepath(key)

        if not os.path.exists(filepath):
            return None

        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            # TTL 확인
            if time.time() - data['timestamp'] > self.ttl:
                os.remove(filepath)
                logger.debug(f"캐시 만료: {key}")
                return None

            # 메모리 캐시에 로드
            self._memory_cache[key] = data
            logger.debug(f"파일 캐시 히트: {key}")
            return data['value']

        except Exception as e:
            logger.error(f"캐시 읽기 오류: {e}")
            return None

    def set(self, key: str, value: Any):
        """
            캐시에 값 저장
        """
        data = {
            'value': value,
            'timestamp': time.time()
        }

        # 메모리 캐시에 저장
        self._memory_cache[key] = data

        # 파일 캐시에 저장
        filepath = self._get_cache_filepath(key)

        try:
            with open(filepath, 'wb') as f:
                pickle.dump(data, f)
            logger.debug(f"캐시 설정: {key}")
        except Exception as e:
            logger.error(f"캐시 쓰기 오류: {e}")

    def delete(self, key: str):
        """
            캐시에서 값 삭제
        """
        # 메모리 캐시에서 삭제
        if key in self._memory_cache:
            del self._memory_cache[key]

        # 파일 캐시에서 삭제
        filepath = self._get_cache_filepath(key)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                logger.debug(f"캐시 삭제: {key}")
            except Exception as e:
                logger.error(f"캐시 삭제 오류: {e}")

    def clear(self):
        """
            모든 캐시 초기화
        """
        # 메모리 캐시 초기화
        self._memory_cache.clear()

        # 파일 캐시 초기화
        for filename in os.listdir(self.cache_dir):
            if filename.endswith('.cache'):
                filepath = os.path.join(self.cache_dir, filename)
                try:
                    os.remove(filepath)
                except Exception as e:
                    logger.error(f"캐시 파일 삭제 실패 {filepath}: {e}")

        logger.info("캐시 초기화 완료")

    def _cleanup_old_cache(self):
        """
            오래된 캐시 파일 정리
        """
        current_time = time.time()
        cleaned_count = 0

        for filename in os.listdir(self.cache_dir):
            if not filename.endswith('.cache'):
                continue

            filepath = os.path.join(self.cache_dir, filename)

            try:
                # 파일 수정 시간 확인
                file_time = os.path.getmtime(filepath)
                if current_time - file_time > self.ttl:
                    os.remove(filepath)
                    cleaned_count += 1
            except Exception as e:
                logger.error(f"캐시 파일 정리 실패 {filepath}: {e}")

        if cleaned_count > 0:
            logger.info(f"만료된 캐시 파일 {cleaned_count}개 정리 완료")

    def get_cache_size(self) -> Dict[str, Any]:
        """
            캐시 크기 정보 반환
        """
        total_size = 0
        file_count = 0

        for filename in os.listdir(self.cache_dir):
            if filename.endswith('.cache'):
                filepath = os.path.join(self.cache_dir, filename)
                total_size += os.path.getsize(filepath)
                file_count += 1

        return {
            'total_size_bytes': total_size,
            'total_size_mb': total_size / (1024 * 1024),
            'file_count': file_count,
            'memory_cache_count': len(self._memory_cache)
        }