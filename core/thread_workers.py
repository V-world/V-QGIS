from PyQt5.QtCore import QThread, pyqtSignal, QObject
from typing import List, Callable, Any, Dict, Optional
import logging
import requests

from ..utils import ApiClient
from ..exceptions import GeocodingError

logger = logging.getLogger(__name__)


class GenericWorker(QThread):
    """
        범용 백그라운드 워커
    """

    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)
    status = pyqtSignal(str)

    def __init__(
            self,
            func: Callable,
            *args,
            progress_callback: Optional[Callable] = None,
            **kwargs
    ):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.progress_callback = progress_callback
        self._is_cancelled = False

    def run(self):
        try:
            self.status.emit("작업 시작...")

            if self.progress_callback:
                self.kwargs['progress_callback'] = self._emit_progress

            result = self.func(*self.args, **self.kwargs)

            if not self._is_cancelled:
                self.finished.emit(result)
                self.status.emit("작업 완료")
        except Exception as e:
            logger.exception(f"워커 오류: {e}")
            self.error.emit(str(e))
            self.status.emit("작업 실패")

    def _emit_progress(self, value: int, message: str = ""):
        """
            진행률 전송
        """
        if not self._is_cancelled:
            self.progress.emit(value)
            if message:
                self.status.emit(message)

    def cancel(self):
        self._is_cancelled = True
        self.terminate()
        self.wait()


class GeocodingWorker(QThread):
    """
        지오코딩 전용 워커
    """

    finished = pyqtSignal(list)
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, addresses: List[str], crs: str):
        super().__init__()
        self.addresses = addresses
        self.crs = crs
        self.api_client = ApiClient()
        self._is_cancelled = False

    def run(self):
        """
            지오코딩 실행
        """
        results = []
        total = len(self.addresses)

        self.status.emit(f"총 {total}개 주소 지오코딩 시작...")

        for idx, address in enumerate(self.addresses):
            if self._is_cancelled:
                break

            try:
                # 진행 상태 업데이트
                self.status.emit(f"처리 중: {address} ({idx + 1}/{total})")

                # 지오코딩 실행
                result = self._geocode_single(address)
                results.append(result)

                # 진행률 업데이트
                progress = int((idx + 1) / total * 100)
                self.progress.emit(progress)

            except Exception as e:
                logger.error(f"{address} 지오코딩 오류: {e}")
                results.append({
                    'address': address,
                    'x': 0,
                    'y': 0,
                    'status': f'오류: {str(e)}'
                })

        if not self._is_cancelled:
            self.finished.emit(results)
            self.status.emit("지오코딩 완료")

    def _geocode_single(self, address: str) -> Dict[str, Any]:
        """
            단일 주소 지오코딩
        """
        try:
            # 도로명 주소로 시도
            response = self.api_client.geocode(address, self.crs)

            if response.get('response', {}).get('status') == 'OK':
                point = response['response']['result']['point']
                return {
                    'address': address,
                    'x': float(point['x']),
                    'y': float(point['y']),
                    'status': '성공'
                }

            # 지번 주소로 재시도
            params = {
                "service": "address",
                "request": "getcoord",
                "crs": self.crs,
                "address": address,
                "format": "json",
                "type": "parcel"
            }

            response = self.api_client.request("/req/address", params).json()

            if response.get('response', {}).get('status') == 'OK':
                point = response['response']['result']['point']
                return {
                    'address': address,
                    'x': float(point['x']),
                    'y': float(point['y']),
                    'status': '성공'
                }

            # 실패
            error_text = response.get('response', {}).get('error', {}).get('text', '주소를 찾을 수 없습니다')
            return {
                'address': address,
                'x': 0,
                'y': 0,
                'status': error_text
            }

        except Exception as e:
            raise GeocodingError(f"지오코딩 실패: {str(e)}")

    def cancel(self):
        self._is_cancelled = True
        self.status.emit("작업 취소됨")


class SearchWorker(QThread):
    """
        주소 검색 전용 워커
    """

    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, query: str, crs: str):
        super().__init__()
        self.query = query
        self.crs = crs
        self.api_client = ApiClient()

    def run(self):
        """
            검색 실행
        """
        try:
            results = []

            # 지번 주소 검색
            response = self.api_client.search_address(self.query, self.crs, 'ADDRESS')

            if response.get('response', {}).get('status') != 'NOT_FOUND':
                items = response.get('response', {}).get('result', {}).get('items', [])
                for item in items:
                    results.append({
                        'address': item['address']['parcel'],
                        'x': float(item['point']['x']),
                        'y': float(item['point']['y']),
                        'type': 'parcel'
                    })

            # 도로명 주소 검색
            if not results:
                params = {
                    "request": "search",
                    "format": "json",
                    "size": "10",
                    "page": "1",
                    "query": self.query,
                    "type": "ADDRESS",
                    "category": "ROAD",
                    "crs": self.crs
                }

                response = self.api_client.request("/req/search", params).json()

                if response.get('response', {}).get('status') != 'NOT_FOUND':
                    items = response.get('response', {}).get('result', {}).get('items', [])
                    for item in items:
                        results.append({
                            'address': item['address']['road'],
                            'x': float(item['point']['x']),
                            'y': float(item['point']['y']),
                            'type': 'road'
                        })

            self.finished.emit(results)

        except Exception as e:
            logger.error(f"검색 오류: {e}")
            self.error.emit(str(e))


class FileProcessWorker(QThread):
    """
        파일 처리 전용 워커
    """

    finished = pyqtSignal(object)
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, file_path: str, process_func: Callable):
        super().__init__()
        self.file_path = file_path
        self.process_func = process_func
        self._is_cancelled = False

    def run(self):
        try:
            self.status.emit(f"파일 처리 시작: {self.file_path}")

            # 진행률 콜백 함수
            def progress_callback(value: int, message: str = ""):
                if not self._is_cancelled:
                    self.progress.emit(value)
                    if message:
                        self.status.emit(message)

            # 파일 처리
            result = self.process_func(
                self.file_path,
                progress_callback=progress_callback
            )

            if not self._is_cancelled:
                self.finished.emit(result)
                self.status.emit("파일 처리 완료")

        except Exception as e:
            logger.error(f"파일 처리 오류: {e}")
            self.error.emit(str(e))
            self.status.emit("파일 처리 실패")

    def cancel(self):
        self._is_cancelled = True
        self.status.emit("작업 취소됨")


class BatchWorker(QThread):
    """
        배치 작업 전용 워커
    """

    finished = pyqtSignal()
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    error = pyqtSignal(str)
    item_completed = pyqtSignal(int, object)  # index, result

    def __init__(self, items: List[Any], process_func: Callable):
        super().__init__()
        self.items = items
        self.process_func = process_func
        self._is_cancelled = False
        self.results = []

    def run(self):
        total = len(self.items)
        self.status.emit(f"총 {total}개 항목 처리 시작...")

        for idx, item in enumerate(self.items):
            if self._is_cancelled:
                break

            try:
                # 아이템 처리
                self.status.emit(f"처리 중: {idx + 1}/{total}")
                result = self.process_func(item)
                self.results.append(result)

                # 아이템 완료 시그널
                self.item_completed.emit(idx, result)

                # 진행률 업데이트
                progress = int((idx + 1) / total * 100)
                self.progress.emit(progress)

            except Exception as e:
                logger.error(f"항목 {idx + 1} 처리 오류: {e}")
                self.error.emit(f"항목 {idx + 1} 처리 실패: {str(e)}")

        if not self._is_cancelled:
            self.finished.emit()
            self.status.emit("배치 작업 완료")

    def cancel(self):
        self._is_cancelled = True
        self.status.emit("작업 취소됨")

    def get_results(self) -> List[Any]:
        return self.results