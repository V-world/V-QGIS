import os

from qgis.PyQt.QtCore import Qt

# 버전 정보
PLUGIN_VERSION = "1.0.0"
PLUGIN_NAME = "VWorld"

# 파일 경로
PLUGIN_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(PLUGIN_DIR, 'datas')
IMAGES_DIR = os.path.join(PLUGIN_DIR, 'images')
RESOURCES_DIR = os.path.join(PLUGIN_DIR, 'resources')

# 파일명
OPTIONS_FILE = os.path.join(DATA_DIR, 'options.json')
SEARCHES_FILE = os.path.join(DATA_DIR, 'recent_searches.json')
FAVORITES_FILE = os.path.join(DATA_DIR, 'wfs_favorites.json')

# 로그 파일 (통합 로깅 → 파일 상시 기록, 설정 창에서 내보내기)
LOG_DIR = os.path.join(DATA_DIR, 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'v-qgis.log')

# 공지 팝업 (네이버 블로그 프롤로그)
NOTICE_URL = "https://blog.naver.com/prologue/PrologueList.naver?blogId=v-world&skinType=&skinId=&from=menu"
NOTICE_BLOG_BASE = "https://blog.naver.com"

# API 관련
API_BASE_URL = "api.vworld.kr"
DEFAULT_PROTOCOL = "https://"
DEFAULT_MAX_FEATURES = 1000
DEFAULT_SEARCH_SIZE = 20
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
    'user_api_key_missing': "엑셀 지오코딩은 호출량이 많아 사용자 본인의 무료 인증키가 필요합니다.\n(배경지도·검색과 달리, 사용량이 본인 계정 기준으로 집계되기 때문입니다)\n옵션 창에서 인증키를 입력해주세요.",
    'no_layer_selected': "선택된 레이어가 없습니다.",
    'no_file_selected': "선택된 파일이 없습니다.",
    'invalid_coordinates': "좌표 입력 형식이 잘못되었습니다.",
    'ssl_error': "옵션에서 '브이월드 호출방식'을 HTTP 또는 HTTPS(보안무시)로 변경해주세요.",
    'layer_creation_failed': "레이어 생성에 실패했습니다.",
    'api_request_failed': "API 요청에 실패했습니다.",
    'no_search_results': "검색 결과가 없습니다.",
    'invalid_api_key': "유효하지 않은 API 키입니다.",
    'geocoding_failed': "지오코딩에 실패했습니다.",
    'encoding_not_supported': "지원하지 않는 인코딩입니다.",
    'no_target_layer': "분할할 대상 레이어를 선택해주세요.",
    'sido_required': "먼저 광역시도를 선택해주세요.",
    'sigungu_required': "먼저 시군구를 선택해주세요.",
    'admin_wfs_failed': "행정구역 경계를 불러오지 못했습니다. API 키와 네트워크 상태를 확인해주세요.",
    'split_no_result': "선택한 범위 안에 포함되는 데이터가 없습니다."
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
    'geocoding': '엑셀 지오코딩',
    'settings': '설정',
    'encoding_change': '인코딩 변경',
    'style_change': '폴리곤 스타일 변경',
    'point_mapping': '포인트 일괄 매핑',
    'admin_split': '행정구역 분할',
    'settings_page_general': '일반',
    'settings_page_network': '네트워크',
    'settings_page_display': '화면 표시',
    'settings_page_about': '정보',
    'notice_title': '공지사항',
    'notice_hide_week': '일주일간 보지 않기',
    'notice_close': '닫기'
}

# 툴바 버튼 표시 모드 (Qt.ToolButtonStyle 매핑)
TOOLBAR_DISPLAY_MODES = {
    'IconOnly':       (Qt.ToolButtonStyle.ToolButtonIconOnly,       '아이콘만'),
    'TextOnly':       (Qt.ToolButtonStyle.ToolButtonTextOnly,       '텍스트만'),
    'TextBesideIcon': (Qt.ToolButtonStyle.ToolButtonTextBesideIcon, '아이콘 + 텍스트 (오른쪽)'),
    'TextUnderIcon':  (Qt.ToolButtonStyle.ToolButtonTextUnderIcon,  '아이콘 + 텍스트 (아래)'),
}
DEFAULT_TOOLBAR_DISPLAY_MODE = 'TextUnderIcon'

# 헤더(브랜드 스트립) 표시 모드
#   standard = 큰 헤더(아이콘 + 제목 + 부제목, 현행)
#   compact  = 요약 헤더(부제목 생략, 얇은 스트립)
HEADER_STYLE_STANDARD = 'standard'
HEADER_STYLE_COMPACT = 'compact'
HEADER_STYLE_MODES = {
    HEADER_STYLE_STANDARD: '표준 (큰 헤더)',
    HEADER_STYLE_COMPACT: '요약 (간단한 헤더)',
}
DEFAULT_HEADER_STYLE = HEADER_STYLE_STANDARD

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

# ---------------------------------------------------------------------------
# 행정구역 분할 (브이월드 WFS 행정경계)
# ---------------------------------------------------------------------------
# 분할 단위 → WFS typename (행정경계 레이어)
ADMIN_WFS_TYPENAMES = {
    'sido':    'lt_c_adsido',   # 광역시도
    'sigungu': 'lt_c_adsigg',   # 시군구
    'emd':     'lt_c_ademd',    # 읍면동
}

# WFS 응답의 '이름' 필드명 후보. 실제 필드는 응답 스키마에서 자동 탐지한다.
ADMIN_NAME_FIELD_CANDIDATES = {
    'sido':    ['ctp_kor_nm', 'ctprvn_nm', 'sido_nm', 'full_nm', 'name'],
    'sigungu': ['sig_kor_nm', 'sigungu_nm', 'full_nm', 'name'],
    'emd':     ['emd_kor_nm', 'emd_nm', 'full_nm', 'name'],
}

# WFS 응답의 '법정동 코드' 필드명 후보. 실제 필드는 응답 스키마에서 자동 탐지한다.
ADMIN_CODE_FIELD_CANDIDATES = {
    'sido':    ['ctprvn_cd', 'sido_cd', 'adm_cd', 'adm_sect_c'],
    'sigungu': ['sig_cd', 'sigungu_cd', 'adm_cd', 'adm_sect_c'],
    'emd':     ['emd_cd', 'adm_cd', 'adm_sect_c'],
}

# 광역시도 목록 (이름, 법정동코드 prefix 집합).
# 강원/전북은 특별자치도 전환에 따라 신·구 코드(42/51, 45/52)가 혼재할 수 있어 둘 다 허용.
# ※ 조회 범위(bbox)는 별도로 번들하지 않는다 — 대상 레이어의 실제 데이터 범위(extent)를
#   bbox로 써서, 데이터가 있는 곳의 행정구역만 정확히 받아 자른다. (prefix로 시도/시군구 한정)
ADMIN_SIDO = [
    ('서울특별시',     ('11',)),
    ('부산광역시',     ('26',)),
    ('대구광역시',     ('27',)),
    ('인천광역시',     ('28',)),
    ('광주광역시',     ('29',)),
    ('대전광역시',     ('30',)),
    ('울산광역시',     ('31',)),
    ('세종특별자치시', ('36',)),
    ('경기도',         ('41',)),
    ('강원특별자치도', ('42', '51')),
    ('충청북도',       ('43',)),
    ('충청남도',       ('44',)),
    ('전북특별자치도', ('45', '52')),
    ('전라남도',       ('46',)),
    ('경상북도',       ('47',)),
    ('경상남도',       ('48',)),
    ('제주특별자치도', ('50',)),
]

# 행정경계 WFS 한 페이지당 피처 수.
# V-World WFS는 count(MAXFEATURES) 상한이 1000이며 초과 시 ServiceException을 반환한다.
# 또한 시군구·시도가 섬 등으로 여러 조각(featureMember)으로 쪼개져 와 한 시도 영역도
# 1000조각을 넘길 수 있으므로, version=2.0.0의 startIndex로 페이지네이션해 모두 받는다.
ADMIN_WFS_PAGE_SIZE = 1000
# V-World WFS는 STARTINDEX 상한도 1000이라, 한 bbox에서 startIndex 0+1000 = 최대 2000조각까지만
# 받을 수 있다. 이를 넘는(섬이 많은) 영역은 bbox를 4분할 재귀(쿼드트리)로 쪼개 모두 받는다.
# 분할 재귀 최대 깊이(4 → 최대 4^4=256 타일). 일반 지역은 분할 없이 1회로 끝난다.
ADMIN_WFS_MAX_DEPTH = 4

# 행정경계 WFS 조회·분할 기준 좌표계.
# 기존에 정상 동작하는 add_wfs_layer()와 동일하게 EPSG:4326을 사용한다.
# (bbox 범위 한정은 직접 만든 bbox 문자열 대신 QgsFeatureRequest.setFilterRect로
#  수행하므로, WFS 축 순서는 QGIS가 알아서 처리한다.)
ADMIN_WFS_CRS = "EPSG:4326"

# 읍면동 bbox 질의 시 경계 누락 방지용 여유 버퍼 (도/degree, 4326 기준 ≈ 1km)
ADMIN_BBOX_BUFFER_DEG = 0.01

# V-World WFS는 BBOX 없이 GetFeature를 보내면 피처를 반환하지 않으므로,
# 전국 단위(시도·시군구) 조회 시 사용할 한국 전역 bbox (xmin,ymin,xmax,ymax / EPSG:4326)
KOREA_BBOX_4326 = (123.5, 32.5, 132.5, 39.0)

