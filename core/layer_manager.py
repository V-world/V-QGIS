from qgis.core import (
    QgsVectorLayer, QgsRasterLayer, QgsProject, QgsFeature, QgsGeometry,
    QgsPointXY, QgsCoordinateReferenceSystem, QgsField, QgsWkbTypes,
    QgsFillSymbol, QgsPalLayerSettings, QgsTextFormat, QgsTextBufferSettings,
    QgsVectorLayerSimpleLabeling, QgsCoordinateTransform, QgsSymbol,
    QgsSimpleFillSymbolLayer, QgsSingleSymbolRenderer, Qgis
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor, QFont
from typing import List, Optional, Tuple, Dict, Any
import logging
import random

from ..constants import (
    SEARCH_RESULT_LAYER, WMTS_LAYER_PREFIX, WMTS_CAPABILITIES_PATH,
    TILE_MATRIX_SET, IMAGE_FORMATS, LABEL_MAPPING, DEFAULT_FILL_COLOR,
    DEFAULT_OUTLINE_WIDTH, DEFAULT_OUTLINE_STYLE, DEFAULT_LABEL_FONT,
    DEFAULT_LABEL_SIZE, API_BASE_URL
)
from ..exceptions import LayerError
from ..utils import ConfigManager
from ..config import API_KEY  # config.py에서 직접 가져오기

logger = logging.getLogger(__name__)


class LayerManager:

    @staticmethod
    def create_point_layer(
            name: str,
            crs: str,
            fields: Optional[List[QgsField]] = None
    ) -> QgsVectorLayer:
        """
            포인트 레이어 생성
        """
        uri = f"Point?crs={crs}"
        layer = QgsVectorLayer(uri, name, "memory")

        if not layer.isValid():
            raise LayerError(f"레이어 생성 실패: {name}")

        if fields:
            provider = layer.dataProvider()
            provider.addAttributes(fields)
            layer.updateFields()

        logger.info(f"포인트 레이어 생성: {name}")
        return layer

    @staticmethod
    def create_polygon_layer(
            name: str,
            crs: str,
            fields: Optional[List[QgsField]] = None
    ) -> QgsVectorLayer:
        """
            폴리곤 레이어 생성
        """
        uri = f"Polygon?crs={crs}"
        layer = QgsVectorLayer(uri, name, "memory")

        if not layer.isValid():
            raise LayerError(f"레이어 생성 실패: {name}")

        if fields:
            provider = layer.dataProvider()
            provider.addAttributes(fields)
            layer.updateFields()

        logger.info(f"폴리곤 레이어 생성: {name}")
        return layer

    @staticmethod
    def add_point_to_layer(
            layer: QgsVectorLayer,
            point: QgsPointXY,
            attributes: Optional[List] = None
    ):
        """
            레이어에 포인트 추가
        """
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPointXY(point))

        if attributes:
            feature.setAttributes(attributes)

        provider = layer.dataProvider()
        provider.addFeature(feature)
        layer.updateExtents()

        logger.debug(f"{layer.name()} 레이어에 포인트 추가 완료")

    @staticmethod
    def get_or_create_layer(
            name: str,
            layer_type: str = "Point",
            crs: Optional[str] = None,
            fields: Optional[List[QgsField]] = None
    ) -> QgsVectorLayer:
        """
            레이어 가져오기 또는 생성
        """
        # 기존 레이어 확인
        existing_layers = QgsProject.instance().mapLayersByName(name)

        if existing_layers:
            layer = existing_layers[0]

            # CRS 확인 및 변경
            if crs and layer.crs().authid() != crs:
                layer.setCrs(QgsCoordinateReferenceSystem(crs))
                logger.info(f"{name} 레이어의 CRS를 {crs}로 업데이트")

            return layer

        # 새 레이어 생성
        if crs is None:
            crs = QgsProject.instance().crs().authid()

        if layer_type == "Point":
            layer = LayerManager.create_point_layer(name, crs, fields)
        elif layer_type == "Polygon":
            layer = LayerManager.create_polygon_layer(name, crs, fields)
        else:
            uri = f"{layer_type}?crs={crs}"
            layer = QgsVectorLayer(uri, name, "memory")

        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            return layer
        else:
            raise LayerError(f"레이어 생성 실패: {name}")

    @staticmethod
    def add_wmts_layer(layer_type: str):
        """
            WMTS 레이어 추가
        """
        config = ConfigManager()

        # config.py의 API_KEY 우선, 없으면 사용자 설정 키
        api_key = API_KEY or config.api_key
        if not api_key:
            raise LayerError("API 키가 설정되지 않았습니다.")

        # 옵션에서 선택한 호출 프로토콜(HTTP/HTTPS) 사용
        protocol, _ = config.protocol

        # WMTS Capabilities URL
        capabilities_url = f"{protocol}{API_BASE_URL}{WMTS_CAPABILITIES_PATH.format(api_key=api_key)}"

        # 레이어 파라미터 설정
        layer_name = layer_type
        image_format = IMAGE_FORMATS.get(layer_type, "image/png")

        # URI 구성
        uri = (
            f"crs=EPSG:3857&"
            f"dpiMode=7&"
            f"format={image_format}&"
            f"layers={layer_name}&"
            f"styles=default&"
            f"tileMatrixSet={TILE_MATRIX_SET}&"
            f"url={capabilities_url}"
        )

        # 레이어 생성
        wmts_layer = QgsRasterLayer(uri, f"{WMTS_LAYER_PREFIX}[{layer_type}]", "wms")

        if not wmts_layer.isValid():
            raise LayerError(f"WMTS 레이어 추가 실패: {layer_type}")

        # 프로젝트에 추가
        QgsProject.instance().addMapLayer(wmts_layer)
        logger.info(f"WMTS 레이어 추가 완료: {layer_type}")

    @staticmethod
    def add_wfs_layer(
            layer_id: str,
            layer_name: str,
            crs: Optional[str] = None,
            max_features: int = 1000,
            bbox: Optional[str] = None
    ) -> QgsVectorLayer:
        """
            WFS 레이어 추가
        """
        # config.py의 API_KEY 사용
        api_key = API_KEY

        if not api_key:
            # config.py에 키가 없으면 ConfigManager에서 가져오기 시도
            config = ConfigManager()
            api_key = config.api_key

        if not api_key:
            raise LayerError("API 키가 설정되지 않았습니다.")

        config = ConfigManager()
        protocol, _ = config.protocol

        if crs is None:
            crs = QgsProject.instance().crs().authid()

        # WFS URL 구성 (QGIS 4: 'request' 파라미터는 더 이상 URI에 포함하지 않음)
        # ※ admin_boundary.py의 raw REST 요청과는 형식·목적이 달라 일부러 분리되어 있음
        #   (저쪽은 EPSG:4326 축순서 문제로 QGIS 공급자를 우회)
        wfs_url = (
            f"maxNumFeatures='{max_features}' "
            f"pagingEnabled='true' "
            f"preferCoordinatesForWfsT11='false' "
            f"restrictToRequestBBOX='1' "
            f"srsname='{crs}' "
            f"typename='{layer_name}' "
            f"url='{protocol}{API_BASE_URL}/req/wfs?key={api_key}&maxfeatures={max_features}' "
            f"version='auto'"
        )

        if bbox:
            wfs_url += f" bbox='{bbox}'"

        # 레이어 생성
        wfs_layer = QgsVectorLayer(wfs_url, layer_id, "WFS")

        if not wfs_layer.isValid():
            # 공급자 오류 메시지에 URI(key= 포함)가 섞일 수 있으므로 반드시 마스킹
            error_msg = (wfs_layer.error().message() or '').replace(api_key, '***')
            raise LayerError(f"WFS 레이어 추가 실패: {error_msg}")

        # 스타일 적용
        LayerManager._apply_wfs_style(wfs_layer, layer_name)

        # 프로젝트에 추가
        QgsProject.instance().addMapLayer(wfs_layer)
        logger.info(f"WFS 레이어 추가 완료: {layer_id}")

        return wfs_layer

    @staticmethod
    def _apply_wfs_style(layer: QgsVectorLayer, layer_name: str):
        """
            WFS 레이어에 스타일 적용
        """
        config = ConfigManager()

        if not config.land_label_style:
            return

        label_field = LABEL_MAPPING.get(layer_name)
        if not label_field:
            return

        # 심볼 설정
        symbol = QgsFillSymbol.createSimple({
            'color': DEFAULT_FILL_COLOR,
            'outline_color': LayerManager._get_random_color(),
            'outline_width': DEFAULT_OUTLINE_WIDTH,
            'outline_style': DEFAULT_OUTLINE_STYLE
        })
        layer.renderer().setSymbol(symbol)

        # 라벨 설정
        label_settings = QgsPalLayerSettings()
        label_settings.fieldName = label_field

        # 라벨 배치 (QGIS 4: scoped enum 사용)
        if hasattr(QgsPalLayerSettings, 'Placement'):
            label_settings.placement = QgsPalLayerSettings.Placement.OverPoint
        elif hasattr(QgsPalLayerSettings, 'OverPoint'):
            label_settings.placement = QgsPalLayerSettings.OverPoint

        # 텍스트 형식
        text_format = QgsTextFormat()
        text_format.setFont(QFont(DEFAULT_LABEL_FONT, DEFAULT_LABEL_SIZE))
        text_format.setColor(QColor(0, 0, 0))

        # 버퍼 설정
        buffer_settings = QgsTextBufferSettings()
        buffer_settings.setEnabled(True)
        buffer_settings.setSize(1)
        buffer_settings.setColor(QColor(255, 255, 255))
        text_format.setBuffer(buffer_settings)

        label_settings.setFormat(text_format)

        # 라벨링 적용
        layer.setLabeling(QgsVectorLayerSimpleLabeling(label_settings))
        layer.setLabelsEnabled(True)

    @staticmethod
    def _get_random_color() -> str:
        """
            랜덤 색상 생성
        """
        r = random.randint(0, 255)
        g = random.randint(0, 255)
        b = random.randint(0, 255)
        return QColor(r, g, b).name()

    @staticmethod
    def apply_polygon_style(layer_names: List[str], color: Optional[QColor] = None) -> int:
        """
            폴리곤 레이어 외곽선 스타일 일괄 적용.
            color가 None이면 레이어마다 랜덤 색, 지정되면 해당 색을 사용.
            실제로 스타일이 적용된 레이어 수를 반환.
        """
        vector_layer_type = getattr(QgsVectorLayer, 'VectorLayer', None)
        if vector_layer_type is None:
            vector_layer_type = Qgis.LayerType.Vector
        polygon_geom_type = getattr(QgsWkbTypes, 'PolygonGeometry', None)
        if polygon_geom_type is None:
            polygon_geom_type = QgsWkbTypes.GeometryType.PolygonGeometry

        styled = 0
        for layer_name in layer_names:
            layers = QgsProject.instance().mapLayersByName(layer_name)
            if not layers:
                continue

            layer = layers[0]
            if (layer.type() != vector_layer_type or
                    layer.geometryType() != polygon_geom_type):
                continue

            # 외곽선 색상 (지정 색 또는 랜덤)
            stroke_color = color if color is not None else QColor(
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(0, 255)
            )

            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            fill_layer = QgsSimpleFillSymbolLayer()
            fill_layer.setStrokeColor(stroke_color)
            fill_layer.setFillColor(QColor(0, 0, 0, 0))  # 투명
            symbol.changeSymbolLayer(0, fill_layer)

            layer.setRenderer(QgsSingleSymbolRenderer(symbol))
            layer.triggerRepaint()
            styled += 1

            logger.info(f"폴리곤 스타일 적용: {layer_name}")

        return styled

    @staticmethod
    def change_layer_encoding(layer_names: List[str], encoding: str):
        """
            레이어 인코딩 변경
        """
        # QGIS 3.17 이상에서 CP949를 MS949로 변경
        if Qgis.QGIS_VERSION_INT >= 31700 and encoding == 'CP949':
            encoding = 'MS949'

        # 레거시 enum이 제거된 빌드(QGIS 4 등)도 호환되도록 폴백 처리
        vector_layer_type = getattr(QgsVectorLayer, 'VectorLayer', None)
        if vector_layer_type is None:
            vector_layer_type = Qgis.LayerType.Vector

        for layer_name in layer_names:
            layers = QgsProject.instance().mapLayersByName(layer_name)
            if not layers:
                continue

            layer = layers[0]
            if layer.type() == vector_layer_type:
                layer.setProviderEncoding(encoding)
                layer.reload()
                logger.info(f"{layer_name} 레이어의 인코딩을 {encoding}으로 변경")