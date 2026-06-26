"""
행정구역(광역시도·시군구·읍면동) 경계 조회 및 데이터 분할 로직.

- 경계 폴리곤은 브이월드 WFS 행정경계 레이어(lt_c_adsido/adsigg/ademd)에서 가져온다.
- 조회는 QGIS WFS 프로바이더 대신 REST GetFeature를 직접 호출(requests)하고 GML을 파싱한다.
  · V-World WFS는 EPSG:4326에서 좌표를 '경도,위도' 순서로 주는데, QGIS WFS 프로바이더는
    4326 축순서(위도,경도)를 적용해 bbox/좌표가 어긋나 0건이 되는 문제가 있다.
  · REST + 직접 파싱은 축순서를 우리가 통제하므로 확실하다.
- 분할(클립)은 QGIS 코어 지오메트리 API(intersection)로 직접 수행한다(스레드 안전).
"""

from typing import List, Dict, Optional, Callable
import xml.etree.ElementTree as ET

from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsGeometry, QgsFeatureRequest, QgsRectangle,
    QgsPointXY, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsProject, QgsWkbTypes,
)

from ..constants import (
    ADMIN_WFS_TYPENAMES, ADMIN_NAME_FIELD_CANDIDATES,
    ADMIN_CODE_FIELD_CANDIDATES, ADMIN_WFS_PAGE_SIZE, ADMIN_WFS_MAX_DEPTH,
    ADMIN_WFS_CRS, ADMIN_BBOX_BUFFER_DEG, KOREA_BBOX_4326,
)
from ..exceptions import LayerError
from ..utils import ApiClient, log_message as _log

# 지오메트리 컨테이너로 인식할 gml 요소(로컬 태그)
_GEOM_TAGS = {
    'MultiPolygon', 'MultiSurface', 'Polygon', 'Surface',
}


def _local(tag: str) -> str:
    """'{namespace}local' → 'local' (네임스페이스 제거)."""
    return tag.rsplit('}', 1)[-1]


# ---------------------------------------------------------------------------
# GML 파싱 (경도,위도 / EPSG:4326)
# ---------------------------------------------------------------------------
def _parse_ring(linear_ring) -> List[QgsPointXY]:
    """gml:LinearRing → QgsPointXY 목록. coordinates/posList 모두 지원."""
    for node in linear_ring.iter():
        ltag = _local(node.tag)
        text = (node.text or '').strip()
        if not text:
            continue
        if ltag == 'coordinates':
            pts = []
            for tup in text.split():
                parts = tup.split(',')
                if len(parts) >= 2:
                    try:
                        pts.append(QgsPointXY(float(parts[0]), float(parts[1])))
                    except ValueError:
                        pass
            return pts
        if ltag == 'posList':
            nums = []
            for tok in text.split():
                try:
                    nums.append(float(tok))
                except ValueError:
                    pass
            return [
                QgsPointXY(nums[i], nums[i + 1])
                for i in range(0, len(nums) - 1, 2)
            ]
    return []


def _parse_polygon(poly) -> List[List[QgsPointXY]]:
    """gml:Polygon → [외곽링, 내부홀...] (각 링은 QgsPointXY 목록)."""
    outer = None
    inners = []
    for boundary in poly:
        lb = _local(boundary.tag)
        ring = None
        for sub in boundary.iter():
            if _local(sub.tag) == 'LinearRing':
                ring = sub
                break
        if ring is None:
            continue
        pts = _parse_ring(ring)
        if not pts:
            continue
        if lb in ('outerBoundaryIs', 'exterior'):
            outer = pts
        elif lb in ('innerBoundaryIs', 'interior'):
            inners.append(pts)

    rings = []
    if outer:
        rings.append(outer)
    rings.extend(inners)
    return rings


def _build_geometry(geom_elem) -> Optional[QgsGeometry]:
    """gml MultiPolygon/Polygon 요소 → QgsGeometry(EPSG:4326)."""
    tag = _local(geom_elem.tag)
    if tag in ('MultiPolygon', 'MultiSurface'):
        polys = []
        for member in geom_elem:
            for poly in member:
                if _local(poly.tag) in ('Polygon', 'Surface'):
                    rings = _parse_polygon(poly)
                    if rings:
                        polys.append(rings)
        if not polys:
            return None
        return QgsGeometry.fromMultiPolygonXY(polys)
    if tag in ('Polygon', 'Surface'):
        rings = _parse_polygon(geom_elem)
        if not rings:
            return None
        return QgsGeometry.fromPolygonXY(rings)
    return None


# ---------------------------------------------------------------------------
# 행정구역 단위 조회 (REST GetFeature)
# ---------------------------------------------------------------------------
def _parse_feature_page(root, name_cands, code_cands, prefixes, acc) -> int:
    """한 페이지(FeatureCollection)의 featureMember를 파싱해 acc에 코드 기준으로 병합.
       이 페이지에서 읽은 featureMember 수를 반환(페이지네이션 종료 판단용)."""
    page_read = 0
    for fm in root.iter():
        if _local(fm.tag) not in ('featureMember', 'member'):
            continue
        members = list(fm)
        if not members:
            continue
        feat = members[0]
        page_read += 1

        fields: Dict[str, str] = {}
        geom_elem = None
        for child in feat:
            subs = list(child)
            if subs and _local(subs[0].tag) in _GEOM_TAGS:
                geom_elem = subs[0]
                continue
            text = (child.text or '').strip()
            if text:
                fields[_local(child.tag).lower()] = text

        code = next(
            (fields[c.lower()] for c in code_cands if c.lower() in fields), ''
        )
        name = next(
            (fields[c.lower()] for c in name_cands if c.lower() in fields), ''
        ) or code

        if prefixes and not any(code.startswith(p) for p in prefixes):
            continue
        if geom_elem is None:
            continue
        geom = _build_geometry(geom_elem)
        if geom is None or geom.isEmpty():
            continue

        key = code or name
        if key in acc:
            merged = acc[key]['geometry'].combine(geom)
            if merged and not merged.isEmpty():
                acc[key]['geometry'] = merged
        else:
            acc[key] = {'code': code, 'name': name, 'geometry': geom}

    return page_read


def _request_page(client, typename, bbox_str, start):
    """WFS 2.0.0 GetFeature 한 페이지 요청. (root_element, error_text) 반환.
       FeatureCollection이 아니면 root=None, error_text에 예외 메시지.
       ※ layer_manager.py의 QGIS 공급자 URI 방식과 별개 - 축순서 문제로 raw REST 사용."""
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typename": typename,
        "srsName": ADMIN_WFS_CRS,
        "bbox": bbox_str,
        "count": str(ADMIN_WFS_PAGE_SIZE),
        "startIndex": str(start),
    }
    response = client.request("/req/wfs", params)
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        raise LayerError(f"행정경계 응답 파싱 실패: {exc}")
    if _local(root.tag) != 'FeatureCollection':
        return None, ' '.join(root.itertext()).strip()
    return root, None


def _quadrants(bbox):
    """bbox(xmin,ymin,xmax,ymax)를 4분할."""
    xmin, ymin, xmax, ymax = bbox
    xm = (xmin + xmax) / 2.0
    ym = (ymin + ymax) / 2.0
    return [
        (xmin, ymin, xm, ym), (xm, ymin, xmax, ym),
        (xmin, ym, xm, ymax), (xm, ym, xmax, ymax),
    ]


def _fetch_bbox(client, typename, bbox, name_cands, code_cands, prefixes,
                acc, depth, is_cancelled, stats):
    """
        한 bbox를 페이지네이션(startIndex 0,1000 → 최대 2000조각)으로 받아 acc에 병합.
        두 페이지가 모두 가득 차면(=2000조각 초과 가능성) bbox를 4분할해 재귀(쿼드트리).
        (V-World는 STARTINDEX 상한이 1000이라 한 bbox로는 2000조각까지만 받을 수 있음)
    """
    if is_cancelled and is_cancelled():
        return
    xmin, ymin, xmax, ymax = bbox
    bbox_str = f"{xmin},{ymin},{xmax},{ymax}"

    second_full = False
    for start in (0, ADMIN_WFS_PAGE_SIZE):
        if is_cancelled and is_cancelled():
            return
        root, err = _request_page(client, typename, bbox_str, start)
        stats['requests'] += 1
        if root is None:
            # startIndex가 데이터 끝을 넘으면 예외가 온다. 첫 페이지면 진짜 오류.
            if start == 0:
                # 서버가 되돌려준 예외 텍스트에 API 키가 섞일 수 있으므로 마스킹
                raise LayerError(f"행정경계 조회 오류: {client._mask_key(err)[:150]}")
            return
        page_read = _parse_feature_page(root, name_cands, code_cands, prefixes, acc)
        stats['read'] += page_read
        if page_read < ADMIN_WFS_PAGE_SIZE:
            return  # 이 bbox는 모두 받음
        if start == ADMIN_WFS_PAGE_SIZE:
            second_full = True

    # 2000조각을 가득 채웠다 → 더 있을 수 있으니 4분할 재귀
    if depth < ADMIN_WFS_MAX_DEPTH:
        for sub in _quadrants(bbox):
            _fetch_bbox(client, typename, sub, name_cands, code_cands,
                        prefixes, acc, depth + 1, is_cancelled, stats)
    else:
        stats['truncated'] = True


def fetch_units(
        level: str,
        prefixes: Optional[tuple] = None,
        rect: Optional[QgsRectangle] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
        stats_out: Optional[Dict] = None,
) -> List[Dict]:
    """
        level 단위의 행정구역을 조회해 [{code, name, geometry, bbox(QgsRectangle)}] 목록 반환.
        - rect(EPSG:4326)로 조회 범위를 한정(없으면 전국 bbox). 좌표는 '경도,위도'로 파싱.
        - prefixes가 주어지면 코드가 해당 prefix 중 하나로 시작하는 단위만 남긴다.
        - V-World WFS의 1000개 count·STARTINDEX 상한(한 bbox당 최대 2000조각)을 우회하기 위해
          bbox 쿼드트리 재귀로 모든 조각을 받고, 같은 코드의 조각들은 하나로 병합한다.
        - stats_out에 dict를 주면 {'requests','read','truncated'} 통계를 채워 준다
          (truncated=True면 분할 상한 도달로 일부 단위가 누락됐을 수 있음).
        ※ 순수 HTTP+파싱이라 백그라운드 스레드에서 호출해도 안전하다.
    """
    typename = ADMIN_WFS_TYPENAMES[level]
    name_cands = ADMIN_NAME_FIELD_CANDIDATES[level]
    code_cands = ADMIN_CODE_FIELD_CANDIDATES[level]

    # 조회 bbox 결정 (lon,lat / EPSG:4326)
    if rect is not None and not rect.isEmpty():
        r = QgsRectangle(rect)
        r.grow(ADMIN_BBOX_BUFFER_DEG)
        bbox = (r.xMinimum(), r.yMinimum(), r.xMaximum(), r.yMaximum())
    else:
        bbox = KOREA_BBOX_4326

    client = ApiClient()
    acc: Dict[str, Dict] = {}
    stats = {'requests': 0, 'read': 0, 'truncated': False}
    _fetch_bbox(client, typename, bbox, name_cands, code_cands,
                prefixes, acc, 0, is_cancelled, stats)

    units = sorted(acc.values(), key=lambda u: (u['code'], u['name']))
    for u in units:
        g = u['geometry']
        # GEOS 연산(intersects/intersection)이 어긋나지 않도록 경계를 유효하게 보정
        if not g.isGeosValid():
            fixed = g.makeValid()
            if fixed is not None and not fixed.isEmpty():
                g = fixed
                u['geometry'] = g
        u['bbox'] = g.boundingBox()

    _log(
        f"행정경계 조회: level={level} 요청={stats['requests']} 읽음={stats['read']} "
        f"단위={len(units)} prefixes={prefixes} "
        f"코드샘플={[u['code'] for u in units[:5]]}"
        + (" [경고:분할 상한 도달-누락 가능]" if stats['truncated'] else "")
    )
    if stats_out is not None:
        stats_out.update(stats)
    return units


# ---------------------------------------------------------------------------
# 분할(클립)
# ---------------------------------------------------------------------------
def _make_output_layer(target_layer: QgsVectorLayer, name: str) -> QgsVectorLayer:
    """대상 레이어와 같은 지오메트리 타입·필드·CRS를 가진 빈 메모리 레이어 생성."""
    geom_token = QgsWkbTypes.displayString(target_layer.wkbType())
    crs = target_layer.crs().authid() or "EPSG:4326"
    out = QgsVectorLayer(f"{geom_token}?crs={crs}", name, "memory")
    if not out.isValid():
        raise LayerError(f"분할 결과 레이어 생성 실패: {name}")
    out.dataProvider().addAttributes(target_layer.fields().toList())
    out.updateFields()
    return out


def _new_feature(out_fields, src_feat, geom, is_multi) -> QgsFeature:
    """대상 피처의 속성을 복사하고 geom을 설정한 출력 피처 생성(멀티 타입 보정)."""
    if is_multi and not geom.isMultipart():
        geom = QgsGeometry(geom)
        geom.convertToMultiType()
    nf = QgsFeature(out_fields)
    nf.setAttributes(src_feat.attributes())
    nf.setGeometry(geom)
    return nf


def _clip_with_boundary(target_layer, boundary, out_name, is_multi):
    """
        boundary(대상 CRS)로 대상 레이어를 잘라 (메모리 레이어, 포함된 원본 fid 집합) 반환.
        포함 피처가 없으면 (None, set()).
    """
    if boundary is None or boundary.isEmpty():
        return None, set()
    out = _make_output_layer(target_layer, out_name)
    out_fields = out.fields()
    covered = set()

    def _collect(request):
        feats = []
        for feat in target_layer.getFeatures(request):
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            if not geom.intersects(boundary):
                continue
            inter = geom.intersection(boundary)
            if inter is None or inter.isEmpty():
                continue
            covered.add(feat.id())
            feats.append(_new_feature(out_fields, feat, inter, is_multi))
        return feats

    new_feats = _collect(QgsFeatureRequest().setFilterRect(boundary.boundingBox()))
    if not new_feats:
        new_feats = _collect(QgsFeatureRequest())
    if not new_feats:
        return None, covered

    out.dataProvider().addFeatures(new_feats)
    out.updateExtents()
    return out, covered


def clip_target(target_layer, boundary_geom, out_name, transform):
    """경계(ADMIN_WFS_CRS)를 대상 CRS로 변환해 잘라낸 메모리 레이어 반환(외부 호환용)."""
    boundary = QgsGeometry(boundary_geom)
    if transform is not None:
        boundary.transform(transform)
    is_multi = QgsWkbTypes.isMultiType(target_layer.wkbType())
    out, _ = _clip_with_boundary(target_layer, boundary, out_name, is_multi)
    return out


def split_layer_by_units(
        target_layer: QgsVectorLayer,
        units: List[Dict],
        progress_cb: Optional[Callable[[int, int], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
) -> List[tuple]:
    """
        units(각 {code,name,geometry})로 대상 레이어를 단위별로 잘라
        [(name, QgsVectorLayer), ...]를 반환. 빈 단위(데이터 없음)는 건너뛴다.
        어떤 단위에도 클립되지 않은 피처(=경계 밖)는 '[미분류] 경계 밖 데이터' 레이어로
        통째로 함께 반환한다. (union/difference 대신 '포함된 fid 추적'으로 안정적으로 판정)
    """
    src_crs = QgsCoordinateReferenceSystem(ADMIN_WFS_CRS)
    dst_crs = target_layer.crs()
    transform = None
    if dst_crs.isValid() and dst_crs.authid() != ADMIN_WFS_CRS:
        transform = QgsCoordinateTransform(
            src_crs, dst_crs, QgsProject.instance().transformContext()
        )
    is_multi = QgsWkbTypes.isMultiType(target_layer.wkbType())

    _log(
        f"행정구역 분할 시작: 대상='{target_layer.name()}' "
        f"CRS={dst_crs.authid()} 피처수={target_layer.featureCount()} 단위수={len(units)}"
    )

    total = len(units)
    results = []
    covered_all = set()
    for idx, unit in enumerate(units):
        if is_cancelled and is_cancelled():
            break
        boundary = QgsGeometry(unit['geometry'])
        if transform is not None:
            boundary.transform(transform)

        clipped, covered = _clip_with_boundary(
            target_layer, boundary, unit['name'], is_multi
        )
        covered_all |= covered
        if clipped is not None and clipped.featureCount() > 0:
            results.append((unit['name'], clipped))
        if progress_cb:
            progress_cb(idx + 1, total)

    # 미분류 = 어떤 단위에도 클립되지 않은 원본 피처(통째로)
    leftover_count = 0
    if not (is_cancelled and is_cancelled()):
        out = _make_output_layer(target_layer, "[미분류] 경계 밖 데이터")
        feats = []
        for feat in target_layer.getFeatures():
            if feat.id() in covered_all:
                continue
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            feats.append(_new_feature(out.fields(), feat, geom, is_multi))
        if feats:
            out.dataProvider().addFeatures(feats)
            out.updateExtents()
            leftover_count = len(feats)
            results.append(("[미분류] 경계 밖 데이터", out))

    _log(
        f"행정구역 분할 끝: 단위 레이어 {len(results) - (1 if leftover_count else 0)}개 "
        f"/ 전체 피처 {target_layer.featureCount()} / 분류됨 {len(covered_all)} "
        f"/ 미분류 {leftover_count}"
    )
    return results
