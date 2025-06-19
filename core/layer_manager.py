from qgis.core import (
    QgsVectorLayer, QgsRasterLayer, QgsProject, QgsFeature, QgsGeometry,
    QgsPointXY, QgsCoordinateReferenceSystem, QgsField, QgsWkbTypes,
    QgsFillSymbol, QgsPalLayerSettings, QgsTextFormat, QgsTextBufferSettings,
    QgsVectorLayerSimpleLabeling, QgsCoordinateTransform, QgsSymbol,
    QgsSimpleFillSymbolLayer, QgsSingleSymbolRenderer
)
from PyQt5.QtCore import QVariant
from PyQt5.QtGui import QColor, QFont
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
        # config.py의 API_KEY 사용
        api_key = API_KEY

        if not api_key:
            # config.py에 키가 없으면 ConfigManager에서 가져오기 시도
            config = ConfigManager()
            api_key = config.api_key

        if not api_key:
            raise LayerError("API 키가 설정되지 않았습니다.")

        # WMTS Capabilities URL
        capabilities_url = f"http://{API_BASE_URL}{WMTS_CAPABILITIES_PATH.format(api_key=api_key)}"

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

        # WFS URL 구성
        wfs_url = (
            f"maxNumFeatures='{max_features}' "
            f"request='GetFeature' "
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
            error_msg = wfs_layer.error().message()
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

        # 라벨 배치
        if hasattr(QgsPalLayerSettings, 'OverPoint'):
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
    def apply_random_style_to_polygons(layer_names: List[str]):
        """
            폴리곤 레이어에 랜덤 스타일 적용
        """
        for layer_name in layer_names:
            layers = QgsProject.instance().mapLayersByName(layer_name)
            if not layers:
                continue

            layer = layers[0]

            if (layer.type() != QgsVectorLayer.VectorLayer or
                    layer.geometryType() != QgsWkbTypes.PolygonGeometry):
                continue

            # 새 심볼 생성
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())

            # 랜덤 색상
            random_color = QColor(
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(0, 255)
            )

            # 심볼 설정
            fill_layer = QgsSimpleFillSymbolLayer()
            fill_layer.setStrokeColor(random_color)
            fill_layer.setFillColor(QColor(0, 0, 0, 0))  # 투명
            symbol.changeSymbolLayer(0, fill_layer)

            # 렌더러 설정
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))
            layer.triggerRepaint()

            logger.info(f"레이어에 랜덤 스타일 적용: {layer_name}")

    @staticmethod
    def change_layer_encoding(layer_names: List[str], encoding: str):
        """
            레이어 인코딩 변경
        """
        from qgis.core import Qgis

        # QGIS 3.17 이상에서 CP949를 MS949로 변경
        if Qgis.QGIS_VERSION_INT >= 31700 and encoding == 'CP949':
            encoding = 'MS949'

        for layer_name in layer_names:
            layers = QgsProject.instance().mapLayersByName(layer_name)
            if not layers:
                continue

            layer = layers[0]
            if layer.type() == QgsVectorLayer.VectorLayer:
                layer.setProviderEncoding(encoding)
                layer.reload()
                logger.info(f"{layer_name} 레이어의 인코딩을 {encoding}으로 변경")