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


class PatientNotFoundError(NotFoundError):
    """Raised when a patient cannot be located by id."""

    error_code: str = "PATIENT_NOT_FOUND"


class WorkSessionNotFoundError(NotFoundError):
    """Raised when a work session cannot be located by id."""

    error_code: str = "WORK_SESSION_NOT_FOUND"
