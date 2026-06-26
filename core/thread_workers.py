from qgis.PyQt.QtCore import QThread, pyqtSignal
from typing import List, Dict, Any
import json
import requests

from ..utils import (
    ApiClient, ConfigManager, parse_first_bcc, upscale_naver_thumb,
    log_info, log_warning, log_error,
)
from ..constants import NOTICE_URL, NOTICE_BLOG_BASE, API_TIMEOUT
from ..exceptions import GeocodingError
from .admin_boundary import fetch_units, split_layer_by_units

_BROWSER_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)


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
        # 엑셀 지오코딩은 반드시 사용자가 옵션에 저장한 API 키로만 동작
        self.api_client = ApiClient(force_user_key=True)
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
                log_error(f"지오코딩 오류: {address}: {e}")
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


class NoticeWorker(QThread):
    """
        시작 공지 전용 워커.
        네이버 블로그 프롤로그 페이지를 받아 첫 <td class="bcc">의
        이미지/링크를 추출하고 이미지 bytes를 다운로드한다.
        실패해도 QGIS 시작을 방해하지 않도록 모든 예외를 잡아 failed로 알린다.
    """

    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def run(self):
        try:
            _, verify_ssl = ConfigManager().protocol

            page = requests.get(
                NOTICE_URL,
                headers={'User-Agent': _BROWSER_UA, 'Accept': 'text/html'},
                timeout=API_TIMEOUT,
                verify=verify_ssl,
            )
            page.raise_for_status()
            if not page.encoding or page.encoding.lower() == 'iso-8859-1':
                page.encoding = page.apparent_encoding

            img_url, link = parse_first_bcc(page.text)
            if not img_url:
                log_info("공지: td.bcc 이미지 없음 (구조 변경 또는 JS 렌더링)")
                self.finished.emit({})
                return

            # 큰 원본(postfiles) 우선, 실패 시 원본 썸네일로 폴백
            image_bytes = None
            for candidate in (upscale_naver_thumb(img_url), img_url):
                if not candidate:
                    continue
                try:
                    img = requests.get(
                        candidate,
                        headers={'User-Agent': _BROWSER_UA, 'Referer': NOTICE_BLOG_BASE},
                        timeout=API_TIMEOUT,
                        verify=verify_ssl,
                    )
                    if (img.status_code == 200 and img.content
                            and img.headers.get('Content-Type', '').startswith('image')):
                        image_bytes = img.content
                        break
                except Exception:
                    continue

            if not image_bytes:
                log_info("공지: 이미지 다운로드 실패")
                self.finished.emit({})
                return

            self.finished.emit({
                'image_bytes': image_bytes,
                'link': link or NOTICE_BLOG_BASE,
            })

        except Exception as e:
            log_info(f"공지 로드 실패: {e}")
            self.failed.emit(str(e))


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
        self._is_cancelled = False

    # 카테고리별: (API category, 결과 type, 주소 필드 키, 로그 라벨)
    _CATEGORIES = (
        ('PARCEL', 'parcel', 'parcel', '지번'),
        ('ROAD', 'road', 'road', '도로명'),
    )

    @staticmethod
    def _response_summary(response: Dict[str, Any]) -> str:
        """V-World 검색 응답의 진단 요약(status/record/page/error).

        QGIS 3·4 동작 차이를 추적하기 위해 0건일 때도 호출해 항상 남긴다.
        """
        if not isinstance(response, dict):
            return f"비-딕셔너리 응답: {type(response).__name__}"
        resp = response.get('response', {}) or {}
        record = resp.get('record', {}) or {}
        page = resp.get('page', {}) or {}
        error = resp.get('error', {}) or {}
        parts = [f"status={resp.get('status')}"]
        if record:
            parts.append(f"record(total={record.get('total')}, current={record.get('current')})")
        if page:
            parts.append(
                f"page(total={page.get('total')}, current={page.get('current')}, "
                f"size={page.get('size')})"
            )
        if error:
            parts.append(
                f"error(code={error.get('code')}, level={error.get('level')}, "
                f"text={error.get('text')})"
            )
        return ', '.join(parts)

    @staticmethod
    def _raw_snapshot(response: Dict[str, Any], limit: int = 1000) -> str:
        """응답 원문을 길이 제한해 문자열로 반환(0건 원인 추적용)."""
        try:
            text = json.dumps(response, ensure_ascii=False)
        except (TypeError, ValueError):
            text = str(response)
        return text[:limit] + ('…(생략)' if len(text) > limit else '')

    @staticmethod
    def _parse_items(response: Dict[str, Any], result_type: str, addr_key: str) -> List[Dict[str, Any]]:
        """검색 응답의 items를 normalized 결과 dict 리스트로 변환 (키 누락 안전 처리)."""
        resp = response.get('response', {})
        if resp.get('status') == 'NOT_FOUND':
            return []

        parsed = []
        items = resp.get('result', {}).get('items', [])
        for item in items:
            address = item.get('address', {}).get(addr_key)
            point = item.get('point', {})
            x, y = point.get('x'), point.get('y')
            if not address or x is None or y is None:
                continue  # 주소·좌표가 비면 스킵 (KeyError/잘못된 항목 방지)
            try:
                parsed.append({
                    'address': address,
                    'x': float(x),
                    'y': float(y),
                    'type': result_type,
                })
            except (TypeError, ValueError):
                continue
        return parsed

    @staticmethod
    def _relevance(query: str, address: str) -> int:
        """검색어와 주소의 매칭 점수 (높을수록 관련도 높음)."""
        q = query.replace(' ', '')
        a = address.replace(' ', '')
        if not q:
            return 0

        score = 0
        if q in a:
            score += 1000  # 검색어를 그대로 포함하면 최상위권
        # 토큰(공백 분리) 포함 비율
        tokens = [t for t in query.split() if t]
        if tokens:
            matched = sum(1 for t in tokens if t in address)
            score += int(100 * matched / len(tokens))
        # 주소 길이가 검색어에 가까울수록 가산 (군더더기 적은 정확 매칭 우대)
        score += max(0, 50 - abs(len(a) - len(q)))
        return score

    def _dedup(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """같은 좌표를 가리키는 항목 중복 제거 (도로명 우선)."""
        priority = {'road': 0, 'parcel': 1}
        best: Dict[tuple, Dict[str, Any]] = {}
        order: List[tuple] = []
        for r in results:
            key = (round(r['x'], 6), round(r['y'], 6))
            if key not in best:
                best[key] = r
                order.append(key)
            else:
                # 우선순위가 더 높은(도로명) 항목으로 교체
                if priority.get(r['type'], 9) < priority.get(best[key]['type'], 9):
                    best[key] = r
        return [best[k] for k in order]

    def run(self):
        """
            검색 실행
        """
        try:
            results = []
            log_info(f"주소 검색 시작: '{self.query}' (crs={self.crs})")

            # 지번·도로명을 모두 조회해 병합 (한쪽에만 결과가 있어도 누락 없이 표시)
            for category, result_type, addr_key, label in self._CATEGORIES:
                if self._is_cancelled:
                    return
                response = self.api_client.search_address(
                    self.query, self.crs, 'ADDRESS', category=category
                )
                if self._is_cancelled:
                    return

                # 응답 요약을 항상 남긴다(도로명은 되는데 지번만 0건인 QGIS 3 사례 추적용)
                log_info(
                    f"주소 검색({label}) 응답[category={category}]: "
                    f"{self._response_summary(response)}"
                )

                parsed = self._parse_items(response, result_type, addr_key)
                results.extend(parsed)
                log_info(f"주소 검색({label}): {len(parsed)}건")

                # 0건이면 원인을 알 수 있도록 응답 원문 일부를 남긴다
                if not parsed:
                    log_warning(
                        f"주소 검색({label}) 0건 - 응답 원문[category={category}]: "
                        f"{self._raw_snapshot(response)}"
                    )

            if self._is_cancelled:
                return

            # 중복 제거 후 관련도순 정렬 (안정 정렬로 카테고리 내 API 순서 유지)
            results = self._dedup(results)
            results.sort(key=lambda r: self._relevance(self.query, r['address']), reverse=True)

            log_info(f"주소 검색 완료: '{self.query}' 총 {len(results)}건")
            self.finished.emit(results)

        except Exception as e:
            if self._is_cancelled:
                return
            log_error(f"주소 검색 오류: '{self.query}': {type(e).__name__}: {e}")
            self.error.emit(str(e))

    def cancel(self):
        """협조적 취소 - run()이 다음 체크포인트에서 시그널 없이 조용히 종료한다."""
        self._is_cancelled = True


class AdminUnitsWorker(QThread):
    """
        행정구역 단위 목록 조회 워커(읍면동 모드에서 시군구 콤보 채우기용).
        REST WFS 조회는 순수 HTTP+파싱이라 스레드에서 안전하다.
        지오메트리는 제외하고 code/name/bbox(QgsRectangle)만 가볍게 전달한다.
    """

    finished = pyqtSignal(list)  # [{'code', 'name', 'rect'(QgsRectangle)}, ...]
    warning = pyqtSignal(str)    # 결과는 있으나 일부 누락 가능성 등 비치명 경고
    error = pyqtSignal(str)

    def __init__(self, level: str, prefixes=None, rect=None):
        super().__init__()
        self.level = level
        self.prefixes = prefixes
        self.rect = rect

    def run(self):
        try:
            stats = {}
            units = fetch_units(self.level, self.prefixes, self.rect, stats_out=stats)
            if stats.get('truncated'):
                log_warning(f"행정구역 목록 일부 누락 가능 (분할 상한 도달, level={self.level})")
                self.warning.emit(
                    "행정구역 경계 일부가 누락되었을 수 있습니다. "
                    "조회 범위를 줄여 다시 시도해 주세요."
                )
            slim = [
                {'code': u['code'], 'name': u['name'], 'rect': u['bbox']}
                for u in units
            ]
            self.finished.emit(slim)
        except Exception as e:
            log_error(f"행정구역 목록 조회 오류: {e}")
            self.error.emit(str(e))


class AdminSplitWorker(QThread):
    """
        행정구역 단위 데이터 분할 워커.
        ① 분할 단위(level) 경계를 WFS로 조회(상위 prefix/bbox로 한정, 페이지네이션) →
        ② 각 단위 폴리곤으로 대상 레이어를 잘라(memory) finished로 결과 묶음 전달.
        ※ 조회·클립 모두 스레드 안전하므로 이 워커에서 일괄 수행한다.
    """

    progress = pyqtSignal(int, int)  # done, total
    status = pyqtSignal(str)
    finished = pyqtSignal(list)      # [(unit_name, QgsVectorLayer), ...]
    warning = pyqtSignal(str)        # 결과는 있으나 일부 누락 가능성 등 비치명 경고
    error = pyqtSignal(str)

    def __init__(self, target_layer, level: str, prefixes=None, rect=None):
        super().__init__()
        self.target_layer = target_layer
        self.level = level
        self.prefixes = prefixes
        self.rect = rect
        self._is_cancelled = False

    def _cancelled(self) -> bool:
        return self._is_cancelled

    def run(self):
        try:
            self.status.emit("행정구역 경계를 불러오는 중...")
            stats = {}
            units = fetch_units(
                self.level, self.prefixes, self.rect, self._cancelled,
                stats_out=stats,
            )
            if self._is_cancelled:
                return
            if stats.get('truncated'):
                log_warning(f"행정구역 경계 일부 누락 가능 (분할 상한 도달, level={self.level})")
                self.warning.emit(
                    "행정구역 경계 일부가 누락되었을 수 있습니다. "
                    "조회 범위를 줄여 다시 시도해 주세요."
                )
            if not units:
                self.finished.emit([])
                return

            self.status.emit(f"{len(units)}개 구역으로 분할하는 중...")
            results = split_layer_by_units(
                self.target_layer,
                units,
                progress_cb=lambda d, t: self.progress.emit(d, t),
                is_cancelled=self._cancelled,
            )

            if not self._is_cancelled:
                self.finished.emit(results)

        except Exception as e:
            log_error(f"행정구역 분할 오류: {e}")
            self.error.emit(str(e))

    def cancel(self):
        self._is_cancelled = True
