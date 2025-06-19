import os

# 버전 정보
PLUGIN_VERSION = "1.0.0"
PLUGIN_NAME = "VWorld"

# 파일 경로
PLUGIN_DIR = os.path.dirname(__file__)
UI_DIR = os.path.join(PLUGIN_DIR, 'ui')
DATA_DIR = os.path.join(PLUGIN_DIR, 'datas')
IMAGES_DIR = os.path.join(PLUGIN_DIR, 'images')
RESOURCES_DIR = os.path.join(PLUGIN_DIR, 'resources')

# 파일명
OPTIONS_FILE = os.path.join(DATA_DIR, 'options.json')
SEARCHES_FILE = os.path.join(DATA_DIR, 'recent_searches.json')
FAVORITES_FILE = os.path.join(DATA_DIR, 'wfs_favorites.json')

# API 관련
API_BASE_URL = "api.vworld.kr"
DEFAULT_PROTOCOL = "https://"
DEFAULT_MAX_FEATURES = 1000
DEFAULT_SEARCH_SIZE = 10
API_TIMEOUT = 30  # seconds

# 레이어 이름
SEARCH_RESULT_LAYER = "브이월드[주소결과]"
GEOCODER_LAYER = "Geocoder"
WMTS_LAYER_PREFIX = "브이월드 지도"

# WMS/WMTS 설정
WMTS_CAPABILITIES_PATH = "/req/wmts/1.0.0/{api_key}/WMTSCapabilities.xml"
TILE_MATRIX_SET = "GoogleMapsCompatible"
IMAGE_FORMATS = {
    "Base": "image/png",
    "Satellite": "image/jpeg",
    "Hybrid": "image/png"
}

# 레이블 매핑
LABEL_MAPPING = {
    'lt_c_landinfobasemap': 'jibun',
    'lp_pa_cbnd_bonbun': 'bonbun',
    'lp_pa_cbnd_bubun': 'jibun',
}

# 에러 메시지
ERROR_MESSAGES = {
    'api_key_missing': "옵션(톱니바퀴)에서 API 키를 입력하세요.",
    'no_layer_selected': "선택된 레이어가 없습니다.",
    'no_file_selected': "선택된 파일이 없습니다.",
    'invalid_coordinates': "좌표 입력 형식이 잘못되었습니다.",
    'ssl_error': "옵션에서 '브이월드 호출방식'을 HTTP 또는 HTTPS(보안무시)로 변경해주세요.",
    'layer_creation_failed': "레이어 생성에 실패했습니다.",
    'api_request_failed': "API 요청에 실패했습니다.",
    'no_search_results': "검색 결과가 없습니다.",
    'invalid_api_key': "유효하지 않은 API 키입니다.",
    'geocoding_failed': "지오코딩에 실패했습니다.",
    'encoding_not_supported': "지원하지 않는 인코딩입니다."
}

# 성공 메시지
SUCCESS_MESSAGES = {
    'layer_added': "레이어가 추가되었습니다.",
    'search_completed': "검색이 완료되었습니다.",
    'geocoding_completed': "지오코딩이 완료되었습니다.",
    'settings_saved': "설정이 저장되었습니다.",
    'encoding_applied': "인코딩이 적용되었습니다."
}

# UI 텍스트
UI_TEXTS = {
    'plugin_menu': '&공간정보 오픈플랫폼(브이월드)',
    'toolbar_name': '브이월드',
    'base_map': '브이월드 일반지도',
    'satellite_map': '브이월드 항공지도',
    'hybrid_map': '브이월드 하이브리드',
    'wfs_layers': '브이월드 주제도',
    'address_search': '주소 검색',
    'reverse_geocoding': '주소 조회',
    'geocoding': '지오코딩',
    'settings': '설정',
    'encoding_change': '인코딩 변경',
    'style_change': '폴리곤 스타일 변경',
    'point_mapping': '포인트 일괄 매핑'
}

# 좌표계
DEFAULT_CRS = "EPSG:4326"
KOREA_CRS = {
    "EPSG:4326": "WGS84",
    "EPSG:3857": "Web Mercator",
    "EPSG:5179": "Korea 2000",
    "EPSG:5174": "Bessel 1841",
    "EPSG:5181": "Korea 2000 Central Belt",
    "EPSG:5186": "Korea 2000 Central Belt 2010"
}

# 인코딩
SUPPORTED_ENCODINGS = ['UTF-8', 'EUC-KR', 'CP949', 'MS949']
DEFAULT_ENCODING = 'UTF-8'

# 스타일 설정
DEFAULT_FILL_COLOR = "0,0,0,1"
DEFAULT_OUTLINE_WIDTH = "0.2"
DEFAULT_OUTLINE_STYLE = "solid"
DEFAULT_LABEL_FONT = "Arial"
DEFAULT_LABEL_SIZE = 10

# 검색 설정
MAX_RECENT_SEARCHES = 10
SEARCH_TYPES = {
    'ADDRESS': 'ADDRESS',
    'PARCEL': 'PARCEL',
    'ROAD': 'ROAD'
}

# 프로토콜 설정
PROTOCOL_OPTIONS = {
    'HTTP': ('http://', True),
    'HTTPS(기본값)': ('https://', True),
    'HTTPS(보안무시)': ('https://', False)
}

