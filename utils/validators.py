import re
from typing import List, Tuple
from ..exceptions import ValidationError


class Validators:

    @staticmethod
    def validate_api_key(api_key: str) -> bool:
        """
            API 키 유효성 검증
        """
        if not api_key:
            return False

        # API 키 형식 검증 (알파벳, 숫자, 하이픈으로 구성된 32자 이상)
        pattern = r'^[A-Za-z0-9\-]{32,}$'
        return bool(re.match(pattern, api_key))

    @staticmethod
    def validate_coordinates(coord_text: str) -> List[Tuple[float, float]]:
        """
            좌표 텍스트 검증 및 파싱
        """
        if not coord_text:
            raise ValidationError("좌표를 입력해주세요.")

        # 공백으로 분리
        parts = coord_text.strip().split()

        if len(parts) % 2 != 0:
            raise ValidationError("좌표는 쌍(경도 위도)으로 입력해야 합니다.")

        coordinates = []

        try:
            for i in range(0, len(parts), 2):
                lon = float(parts[i])
                lat = float(parts[i + 1])

                # 한국 좌표 범위 검증 (대략적인 범위)
                if not (124 <= lon <= 132 and 33 <= lat <= 39):
                    # 다른 좌표계일 수 있으므로 경고만
                    pass

                coordinates.append((lon, lat))

        except ValueError:
            raise ValidationError("유효하지 않은 좌표값이 포함되어 있습니다.")

        return coordinates

    @staticmethod
    def validate_crs(crs: str) -> bool:
        """
            좌표계 유효성 검증
        """
        if not crs:
            return False

        # EPSG 코드 형식 검증
        pattern = r'^EPSG:\d+$'
        return bool(re.match(pattern, crs))

    @staticmethod
    def validate_layer_name(name: str) -> bool:
        """
            레이어 이름 유효성 검증
        """
        if not name:
            return False

        # 특수 문자 검증
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']

        for char in invalid_chars:
            if char in name:
                return False

        return True