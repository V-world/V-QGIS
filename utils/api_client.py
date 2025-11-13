import requests
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional
import logging

from ..constants import API_BASE_URL, API_TIMEOUT, DEFAULT_SEARCH_SIZE
from ..exceptions import ApiError, SSLError, AuthenticationError
from ..config import API_KEY  # config.py에서 직접 가져오기
from .config_manager import ConfigManager

logger = logging.getLogger(__name__)


class ApiClient:
    def __init__(self):
        self.config = ConfigManager()
        # config.py의 API_KEY를 우선 사용
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

    def request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        """
            API 요청
        """
        if not self.api_key:
            raise AuthenticationError("API 키가 설정되지 않았습니다.")

        # 파라미터에 API 키 추가
        if params is None:
            params = {}
        params['key'] = self.api_key

        url = f"{self.base_url}{endpoint}"
        _, verify_ssl = self.config.protocol

        try:
            response = requests.get(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=self.timeout,
                verify=verify_ssl
            )

            response.raise_for_status()
            return response

        except requests.exceptions.SSLError as e:
            logger.error(f"SSL 오류: {e}")
            raise SSLError("SSL 인증 오류가 발생했습니다. 설정에서 프로토콜을 변경해주세요.")
        except requests.exceptions.Timeout:
            raise ApiError("요청 시간이 초과되었습니다.")
        except requests.exceptions.RequestException as e:
            logger.error(f"API 요청 실패: {e}")
            raise ApiError(f"API 요청 실패: {str(e)}")

    def _validate_json_response(self, data: Dict[str, Any], endpoint: str) -> Dict[str, Any]:
        """
            JSON 응답 검증

            Args:
                data: JSON 응답 데이터
                endpoint: API 엔드포인트 (로깅용)

            Returns:
                검증된 데이터

            Raises:
                ApiError: 응답이 유효하지 않은 경우
        """
        # 빈 응답 체크
        if not data:
            raise ApiError(f"빈 응답 수신: {endpoint}")

        # 에러 응답 체크
        if 'error' in data:
            error_msg = data.get('error', {})
            if isinstance(error_msg, dict):
                error_text = error_msg.get('text', 'Unknown error')
            else:
                error_text = str(error_msg)
            raise ApiError(f"API 에러: {error_text}")

        # status 체크 (일부 API는 status 필드 사용)
        if 'status' in data and data['status'] in ['error', 'fail', 'ERROR', 'FAIL']:
            error_msg = data.get('message', 'Unknown error')
            raise ApiError(f"API 에러: {error_msg}")

        return data

    def search_address(self, query: str, crs: str = "EPSG:4326", search_type: str = "ADDRESS", size: int = DEFAULT_SEARCH_SIZE) -> Dict[str, Any]:
        """
            주소 검색
        """
        params = {
            "request": "search",
            "format": "json",
            "size": str(size),
            "page": "1",
            "query": query,
            "type": search_type,
            "crs": crs
        }

        response = self.request("/req/search", params)
        data = response.json()
        return self._validate_json_response(data, "/req/search")

    def reverse_geocode(self, x: float, y: float, crs: str = "EPSG:4326") -> Dict[str, Any]:
        """
            역지오코딩
        """
        params = {
            "request": "getAddress",
            "format": "json",
            "crs": crs,
            "point": f"{x},{y}",
            "type": "both"
        }

        response = self.request("/req/address", params)
        data = response.json()
        return self._validate_json_response(data, "/req/address")

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
        data = response.json()
        return self._validate_json_response(data, "/req/address")

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
        return ET.fromstring(response.content)