class VWorldError(Exception):
    """VWorld 플러그인 기본 예외"""
    pass


class ApiError(VWorldError):
    """API 관련 예외"""
    pass


class SSLError(ApiError):
    """SSL 관련 예외"""
    pass


class AuthenticationError(ApiError):
    """인증 관련 예외"""
    pass


class ValidationError(VWorldError):
    """입력 검증 예외"""
    pass


class LayerError(VWorldError):
    """레이어 관련 예외"""
    pass


class FileError(VWorldError):
    """파일 처리 예외"""
    pass


class ConfigurationError(VWorldError):
    """설정 관련 예외"""
    pass


class NetworkError(VWorldError):
    """네트워크 관련 예외"""
    pass


class GeocodingError(VWorldError):
    """지오코딩 관련 예외"""
    pass
