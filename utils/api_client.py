import time
import requests
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional

from ..constants import API_BASE_URL, API_TIMEOUT, DEFAULT_SEARCH_SIZE
from ..exceptions import ApiError, SSLError, AuthenticationError
from ..config import API_KEY  # config.py에서 직접 가져오기
from .config_manager import ConfigManager
from .logger import log_info, log_error


class ApiClient:
    def __init__(self, force_user_key: bool = False):
        self.config = ConfigManager()
        # force_user_key=True 면 config.py 무시하고 사용자가 옵션에 저장한 키만 사용
        # (엑셀 지오코딩 등 사용자 본인 키가 강제되는 기능 전용)
        if force_user_key:
            self.api_key = self.config.user_api_key
        else:
            self.api_key = API_KEY if API_KEY else self.config.api_key
        self.base_url = self._get_base_url()
        self.timeout = API_TIMEOUT

    def _get_base_url(self) -> str:
        """
            기본 URL 생성
        """
        protocol, verify_ssl = self.config.protocol
        return f"{protocol}{API_BASE_URL}"

    def _get_headers(self) -> Dict[str, str]:
        """
            요청 헤더 생성
        """
        return {
            'User-Agent': 'QGIS VWorld Plugin/1.0',
            'Accept': 'application/json'
        }

    def _mask_key(self, text: str) -> str:
        """로그에 API 키가 노출되지 않도록 마스킹"""
        if self.api_key:
            text = text.replace(self.api_key, '***')
        return text

    def request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        """
            API 요청
        """
        if not self.api_key:
            log_error(f"API 요청 차단: API 키 미설정 (endpoint={endpoint})")
            raise AuthenticationError("API 키가 설정되지 않았습니다.")

        # 파라미터에 API 키 추가
        if params is None:
            params = {}
        params['key'] = self.api_key

        url = f"{self.base_url}{endpoint}"
        _, verify_ssl = self.config.protocol

        log_params = {k: v for k, v in params.items() if k != 'key'}
        log_info(f"API 요청: {url} params={log_params}")

        started = time.perf_counter()
        try:
            response = requests.get(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=self.timeout,
                verify=verify_ssl
            )

            response.raise_for_status()
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            log_info(f"API 응답: {endpoint} HTTP {response.status_code} ({elapsed_ms}ms)")
            return response

        except requests.exceptions.SSLError as e:
            log_error(f"API SSL 오류: {endpoint}: {self._mask_key(str(e))}")
            raise SSLError("SSL 인증 오류가 발생했습니다. 설정에서 프로토콜을 변경해주세요.")
        except requests.exceptions.Timeout:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            log_error(f"API 시간 초과: {endpoint} ({elapsed_ms}ms 경과, 제한 {self.timeout}초)")
            raise ApiError("요청 시간이 초과되었습니다.")
        except requests.exceptions.RequestException as e:
            status = getattr(getattr(e, 'response', None), 'status_code', None)
            log_error(f"API 요청 실패: {endpoint} (HTTP {status}): {self._mask_key(str(e))}")
            raise ApiError(f"API 요청 실패: {self._mask_key(str(e))}")

    def search_address(self, query: str, crs: str = "EPSG:4326", search_type: str = "ADDRESS", size: int = DEFAULT_SEARCH_SIZE, category: Optional[str] = None) -> Dict[str, Any]:
        """
            주소 검색

            category: 'PARCEL'(지번) / 'ROAD'(도로명) 등. None이면 API 기본값.
        """
        params = {
            "service": "search",
            "request": "search",
            "format": "json",
            "size": str(size),
            "page": "1",
            "query": query,
            "type": search_type,
            "crs": crs
        }
        if category:
            params["category"] = category

        response = self.request("/req/search", params)
        return response.json()

    def reverse_geocode(self, x: float, y: float, crs: str = "EPSG:4326") -> Dict[str, Any]:
        """
            역지오코딩
        """
        params = {
            "service": "address",
            "request": "getAddress",
            "format": "json",
            "crs": crs,
            "point": f"{x},{y}",
            "type": "both"
        }

        response = self.request("/req/address", params)
        return response.json()

    def geocode(self, address: str, crs: str = "EPSG:4326") -> Dict[str, Any]:
        """
            지오코딩
        """
        params = {
            "service": "address",
            "request": "getcoord",
            "crs": crs,
            "address": address,
            "format": "json",
            "type": "road"
        }

        response = self.request("/req/address", params)
        return response.json()

    def get_wfs_capabilities(self) -> ET.Element:
        """
            WFS Capabilities 가져오기
        """
        params = {
            "service": "WFS",
            "request": "GetCapabilities",
            "version": "1.1.0"
        }

        response = self.request("/req/wfs", params)
        root = ET.fromstring(response.content)
        # 잘못된 키여도 HTTP 200 + ServiceExceptionReport XML이 오므로 여기서 구분한다.
        tag = root.tag.rsplit('}', 1)[-1]
        if tag in ('ServiceExceptionReport', 'ExceptionReport'):
            detail = ' '.join(root.itertext()).strip()[:200]
            log_error(f"WFS Capabilities 서비스 예외: {self._mask_key(detail)}")
            raise AuthenticationError("API 키가 올바르지 않거나 사용 승인되지 않았습니다.")
        return root