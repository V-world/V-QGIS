# Changelog

All notable changes to the V-World QGIS Plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2025-01-13

### Added
- **.env 파일 지원**: 사용자 개인 API 키를 .env 파일에 안전하게 저장
  - 우선순위: `.env` > `config.py` > `QSettings`
  - `FileManager`에 `.env` 파일 읽기/쓰기 메서드 추가
  - `constants.py`에 `ENV_FILE` 경로 추가
- **API 응답 검증**: API 요청 후 응답 유효성 검증 로직 추가
  - `ApiClient._validate_json_response()` 메서드 추가
  - 빈 응답, 에러 응답, 상태 코드 검증
- **좌표계 변환 오류 처리**: 좌표계 변환 시 예외 처리 강화
  - 원본/대상 좌표계 유효성 확인
  - 변환 실패 시 사용자 친화적 에러 메시지
- **매직 넘버 상수화**: 하드코딩된 값들을 상수로 정의
  - `DATA_ROLE_X`, `DATA_ROLE_Y`, `DATA_ROLE_TYPE`, `DATA_ROLE_CRS` 추가
  - `WORKER_QUIT_TIMEOUT`, `WORKER_TERMINATE_TIMEOUT` 추가
- **누락된 위젯 구현 가이드**: `TODO_MISSING_WIDGETS.md` 문서 추가
  - GeocoderWidget, EncodingWidget, StyleChangeWidget 구현 계획

### Changed
- **API 키 관리 개선**
  - `config.py`: 기본 공용 API 키로 명확히 표시 (주석 추가)
  - `ConfigManager.api_key`: .env 파일 우선 읽기 로직 추가
  - 사용자가 설정 대화상자에서 입력한 API 키는 자동으로 .env에 저장
- **번역 파일 로드 개선**
  - `v_world.py._setup_translator()`: None 체크 추가
  - 기본값 'ko_KR' 설정
  - 예외 처리 추가로 안정성 향상
- **SearchWorker 종료 처리 개선**
  - `terminate()` 대신 `quit()` 우선 사용 (정상 종료)
  - 5초 타임아웃 후 강제 종료
  - 리소스 누수 방지

### Fixed
- **.gitignore merge conflict 해결**
  - 병합 충돌 마커 제거
  - IDE, OS, 빌드 관련 항목 추가
  - `.env` 파일 제외 추가
- **디렉토리 생성 보장**: `FileManager`에서 자동으로 상위 디렉토리 생성
  - `write_json()`, `write_text()` 호출 시 자동 처리
  - 파일 저장 실패 방지

### Security
- **API 키 보안 강화**
  - 개인 API 키는 .env 파일에 저장 (Git에서 제외)
  - 기본 공용 API 키는 `config.py`에 유지 (테스트용)
  - `.gitignore`에 `.env`, `.env.local` 추가

### Deprecated
- `QSettings`에 직접 API 키 저장 방식 (레거시 지원은 유지)

---

## [1.0.0] - 2024-XX-XX

### Initial Release
- V-World WMTS 지도 레이어 지원 (일반/항공/하이브리드)
- WFS 주제도 레이어 지원 (100개 이상)
- 주소 검색 기능
- 역지오코딩 기능
- 지오코딩 기능
- 레이어 인코딩 변경
- 폴리곤 스타일 변경
- 포인트 일괄 매핑
- 최근 검색 기록 저장
- WFS 레이어 즐겨찾기
- 2단계 캐시 시스템 (메모리 + 파일)
- 백그라운드 작업 워커
- SSL 인증서 옵션
- 프로토콜 선택 (HTTP/HTTPS)

---

## 작업 중인 이슈

### 누락된 위젯 파일들
다음 위젯들의 Python 파일이 누락되어 현재 기능하지 않습니다:
- ❌ `widgets/geocoder_widget.py` - 지오코딩 위젯
- ❌ `widgets/encoding_widget.py` - 인코딩 변경 위젯
- ❌ `widgets/style_widget.py` - 스타일 변경 위젯

**해결 방법**: `TODO_MISSING_WIDGETS.md` 참조

---

## 버전 관리 정책

### 버전 번호 규칙
- **MAJOR**: 호환되지 않는 API 변경
- **MINOR**: 하위 호환되는 기능 추가
- **PATCH**: 하위 호환되는 버그 수정

### 릴리스 주기
- **Stable**: 주요 기능 완성 및 충분한 테스트 후
- **Beta**: 새로운 기능 추가 시
- **Hotfix**: 긴급 버그 수정 시

---

## 참고 링크
- [V-World 공식 사이트](https://www.vworld.kr)
- [V-World API 문서](https://www.vworld.kr/dev/v4dv_2ddataguide2_s001.do)
- [GitHub Repository](https://github.com/qbong1010/V-QGIS)
