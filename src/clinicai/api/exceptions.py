"""Domain API exceptions for ClinicAI."""

from clinicai.core.exceptions import ClinicAIBaseException


class NotFoundError(ClinicAIBaseException):
    """Raised when a resource is not found (HTTP 404)."""

    status_code: int = 404
    error_code: str = "NOT_FOUND"


class ValidationError(ClinicAIBaseException):
    """Raised when domain validation fails (HTTP 422)."""

    status_code: int = 422
    error_code: str = "VALIDATION_ERROR"


class ConflictError(ClinicAIBaseException):
    """Raised when a state conflict occurs (HTTP 409)."""

    status_code: int = 409
    error_code: str = "CONFLICT_ERROR"


class BillChangedError(ConflictError):
    """Hoá đơn máy chủ tính lại khác hoá đơn thu ngân đang nhìn (HTTP 409).

    Contract tiền–thuốc C3: không thu theo số cũ — giao diện phải tải lại.
    """

    error_code: str = "BILL_CHANGED"


class AIDisabledError(ClinicAIBaseException):
    """Tính năng AI chưa bật (thiếu ANTHROPIC_API_KEY) — HTTP 503.

    AI đứng SAU cờ (15/09/2026): thiếu khoá thì cả API vẫn chạy, chỉ những
    endpoint cần mô hình trả câu này. Trước đó `AnthropicClient()` ném lỗi ngay
    lúc khởi động và cả phòng khám mất hệ thống vì một tính năng phụ.
    """

    status_code: int = 503
    error_code: str = "AI_DISABLED"


class PatientNotFoundError(NotFoundError):
    """Raised when a patient cannot be located by id."""

    error_code: str = "PATIENT_NOT_FOUND"


class WorkSessionNotFoundError(NotFoundError):
    """Raised when a work session cannot be located by id."""

    error_code: str = "WORK_SESSION_NOT_FOUND"
