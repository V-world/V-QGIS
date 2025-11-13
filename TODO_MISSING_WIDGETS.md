# 누락된 위젯 구현 계획

## 개요
V-QGIS 플러그인에서 3개의 위젯 파일이 누락되어 있습니다. 이 문서는 각 위젯의 구현 계획을 정리합니다.

## 1. GeocoderWidget (지오코딩 위젯)

### 파일 위치
- **Python 파일**: `widgets/geocoder_widget.py`
- **UI 파일**: `ui/v_world_dockGeocoder_base.ui` ✅ (존재함)
- **참조 위치**: `v_world.py:292`

### 기능 요구사항
1. **주소 → 좌표 변환**
   - 주소 입력 필드
   - 검색 버튼
   - 좌표 결과 표시

2. **배치 지오코딩**
   - 텍스트 파일 업로드 (주소 목록)
   - 진행률 표시 바
   - 결과 테이블 뷰
   - CSV 내보내기 기능

3. **좌표계 선택**
   - QgsProjectionSelectionWidget 통합
   - EPSG:4326, EPSG:3857, EPSG:5179 등 지원

### 클래스 구조
```python
class GeocoderWidget(BaseWidget, FORM_CLASS):
    def __init__(self, parent=None):
        # 초기화

    def _geocode_single(self, address: str):
        # 단일 주소 지오코딩

    def _geocode_batch(self, addresses: List[str]):
        # 배치 지오코딩 (GeocodingWorker 사용)

    def _export_to_csv(self, results: List[Dict]):
        # 결과를 CSV로 저장
```

### 의존성
- `utils.ApiClient` - geocode() 메서드
- `core.GeocodingWorker` - 백그라운드 배치 처리
- `core.LayerManager` - 결과 레이어 생성

---

## 2. EncodingWidget (인코딩 변경 위젯)

### 파일 위치
- **Python 파일**: `widgets/encoding_widget.py`
- **UI 파일**: `ui/v_world_dockEncode_base.ui` ✅ (존재함)
- **참조 위치**: `v_world.py:308`

### 기능 요구사항
1. **레이어 선택**
   - 현재 프로젝트의 벡터 레이어 목록 표시
   - 다중 선택 지원

2. **인코딩 선택**
   - UTF-8
   - EUC-KR
   - CP949 / MS949 (QGIS 3.17+ 자동 변환)

3. **적용 버튼**
   - 선택된 레이어에 인코딩 적용
   - 레이어 자동 리로드
   - 성공/실패 메시지 표시

### 클래스 구조
```python
class EncodingWidget(BaseWidget, FORM_CLASS):
    def __init__(self, parent=None):
        # 초기화

    def refresh_layer_list(self):
        # 레이어 목록 새로고침

    def _apply_encoding(self):
        # 선택된 레이어에 인코딩 적용
        # LayerManager.change_layer_encoding() 사용
```

### 의존성
- `core.LayerManager.change_layer_encoding()`
- `constants.SUPPORTED_ENCODINGS`

### 특별 고려사항
- QGIS 버전에 따른 CP949/MS949 처리 (이미 LayerManager에 구현됨)

---

## 3. StyleChangeWidget (폴리곤 스타일 변경 위젯)

### 파일 위치
- **Python 파일**: `widgets/style_widget.py`
- **UI 파일**: `ui/v_world_dockStyleChange_base.ui` ✅ (존재함)
- **참조 위치**: `v_world.py:325`

### 기능 요구사항
1. **폴리곤 레이어 선택**
   - 현재 프로젝트의 폴리곤 레이어만 필터링
   - 다중 선택 지원

2. **스타일 옵션**
   - 랜덤 색상 적용
   - 투명 채우기 옵션
   - 외곽선 색상 선택
   - 외곽선 두께 설정

3. **미리보기**
   - 색상 미리보기 (선택 사항)

### 클래스 구조
```python
class StyleChangeWidget(BaseWidget, FORM_CLASS):
    def __init__(self, parent=None):
        # 초기화

    def refresh_layer_list(self):
        # 폴리곤 레이어 목록 새로고침

    def _apply_random_style(self):
        # 랜덤 스타일 적용
        # LayerManager.apply_random_style_to_polygons() 사용

    def _apply_custom_style(self, color, width):
        # 커스텀 스타일 적용
```

### 의존성
- `core.LayerManager.apply_random_style_to_polygons()`
- `qgis.core.QgsWkbTypes.PolygonGeometry`

---

## 구현 우선순위

### 1순위: EncodingWidget (가장 단순)
- 기능이 명확하고 단순함
- LayerManager에 이미 구현된 메서드 활용
- 예상 작업 시간: 1-2시간

### 2순위: StyleChangeWidget
- 기능이 명확하고 단순함
- LayerManager에 이미 구현된 메서드 활용
- 추가 스타일 옵션 가능
- 예상 작업 시간: 2-3시간

### 3순위: GeocoderWidget (가장 복잡)
- 배치 처리 기능 필요
- 파일 I/O 및 진행률 표시
- CSV 내보내기 기능
- 예상 작업 시간: 4-6시간

---

## 구현 템플릿

### 기본 위젯 템플릿
```python
import os
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
import logging

from .base_widget import BaseWidget
from ..constants import UI_DIR
from ..utils import with_error_handling

logger = logging.getLogger(__name__)

FORM_CLASS, _ = uic.loadUiType(os.path.join(UI_DIR, 'v_world_dock{NAME}_base.ui'))


class {NAME}Widget(BaseWidget, FORM_CLASS):
    """
        {설명}
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self._connect_signals()

    def _connect_signals(self):
        """
            시그널 연결
        """
        # TODO: 버튼 및 이벤트 연결
        pass

    @with_error_handling("{기능} 중 오류가 발생했습니다")
    def _main_function(self):
        """
            주요 기능 구현
        """
        # TODO: 기능 구현
        pass
```

---

## 테스트 계획

### 각 위젯 공통 테스트
1. ✅ 위젯이 정상적으로 열리는지
2. ✅ UI 요소들이 올바르게 표시되는지
3. ✅ 기능 실행 시 예외가 발생하지 않는지
4. ✅ 에러 메시지가 사용자 친화적인지

### 위젯별 특수 테스트
- **GeocoderWidget**: 대용량 배치 처리 (1000개 이상 주소)
- **EncodingWidget**: 다양한 인코딩 조합 테스트
- **StyleChangeWidget**: 다양한 지오메트리 타입 처리

---

## 완료 체크리스트

### EncodingWidget
- [ ] Python 파일 생성
- [ ] UI 연결
- [ ] 레이어 목록 표시
- [ ] 인코딩 적용 기능
- [ ] 에러 처리
- [ ] 테스트
- [ ] v_world.py 통합 확인

### StyleChangeWidget
- [ ] Python 파일 생성
- [ ] UI 연결
- [ ] 폴리곤 레이어 필터링
- [ ] 랜덤 스타일 적용
- [ ] 에러 처리
- [ ] 테스트
- [ ] v_world.py 통합 확인

### GeocoderWidget
- [ ] Python 파일 생성
- [ ] UI 연결
- [ ] 단일 지오코딩 기능
- [ ] 배치 지오코딩 기능
- [ ] 진행률 표시
- [ ] CSV 내보내기
- [ ] 에러 처리
- [ ] 테스트
- [ ] v_world.py 통합 확인

---

## 참고 사항

- 모든 위젯은 `BaseWidget`을 상속받아야 함
- `@with_error_handling` 데코레이터 활용 권장
- 로깅을 적극 활용하여 디버깅 용이성 확보
- 사용자에게 적절한 피드백 제공 (메시지 박스, 진행률 바)
