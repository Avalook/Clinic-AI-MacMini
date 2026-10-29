"""Custom exception hierarchy for ClinicAI."""


class ClinicAIBaseException(Exception):  # noqa: N818
    """Base exception for all ClinicAI errors."""

    status_code: int = 400
    error_code: str = "BAD_REQUEST"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ResourceNotFoundError(ClinicAIBaseException):
    """Raised when a requested resource is not found (HTTP 404)."""

    status_code: int = 404
    error_code: str = "NOT_FOUND"


class ValidationError(ClinicAIBaseException):
    """Raised when request data fails validation (HTTP 422)."""

    status_code: int = 422
    error_code: str = "VALIDATION_ERROR"


class ChuaThuTienError(ValidationError):
    """Chưa thu tiền nên chưa làm / chưa hoàn tất được (HTTP 422) — mã riêng để
    màn vẽ thành LỜI NHẮC (màu vàng), không phải lỗi đỏ (Tuyền 29/10/2026)."""

    error_code: str = "CHUA_THU_TIEN"


class SafetyGateError(ClinicAIBaseException):
    """Raised when a business/safety gate condition is violated (HTTP 403)."""

    status_code: int = 403
    error_code: str = "SAFETY_GATE_ERROR"


class ExternalServiceError(ClinicAIBaseException):
    """Raised when an external service integration fails (HTTP 502)."""

    status_code: int = 502
    error_code: str = "EXTERNAL_SERVICE_ERROR"
