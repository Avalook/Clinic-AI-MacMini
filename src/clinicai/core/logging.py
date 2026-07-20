"""Structured logging configuration for ClinicAI.

Log lines are JSON with auto-injected fields:
  - ``request_id``  (from RequestIdMiddleware via contextvars)
  - ``service``     (always "clinicai-api")
  - ``environment`` (from APP_ENV, default "development")
  - ``timestamp``   (ISO 8601)
  - ``log_level``   (INFO, WARNING, ERROR, etc.)
"""

import logging
import os
import re
import sys
from collections.abc import Mapping
from typing import Any, Dict

import structlog

REDACTED = "[REDACTED]"

_SENSITIVE_KEYS = frozenset(
    {
        "access_token",
        "address",
        "api_key",
        "authorization",
        "cookie",
        "email",
        "full_name",
        "guardian_name",
        "message",
        "message_preview",
        "password",
        "patient_code",
        "patient_id",
        "patient_name",
        "clinic_patient_id",
        "phone",
        "phone_number",
        "prompt",
        "raw_text",
        "reasoning",
        "refresh_token",
        "response_text",
        "secret",
        "service_role_key",
        "set_cookie",
        "short_name",
        "system_prompt",
        "transcript",
        "user_prompt",
    }
)
_SENSITIVE_KEY_SUFFIXES = (
    "_address",
    "_email",
    "_full_name",
    "_message",
    "_password",
    "_patient_id",
    "_phone",
    "_prompt",
    "_secret",
    "_token",
    "_transcript",
)
_EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w.-])")
_VN_PHONE_RE = re.compile(r"(?<!\d)(?:\+?84|0)(?:[ .-]?\d){8,10}(?!\d)")
_BEARER_RE = re.compile(r"(?i)\b(?:authorization\s*[:=]\s*)?bearer\s+[a-z0-9._~+/=-]+")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)"
    r"\s*[:=]\s*[^\s,;]+"
)


def _redact_text(value: str) -> str:
    """Remove common secrets and direct contact identifiers from free text."""
    value = _BEARER_RE.sub(REDACTED, value)
    value = _SECRET_ASSIGNMENT_RE.sub(REDACTED, value)
    value = _EMAIL_RE.sub(REDACTED, value)
    return _VN_PHONE_RE.sub(REDACTED, value)


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).lower().replace("-", "_").replace(".", "_")
    return normalized in _SENSITIVE_KEYS or normalized.endswith(_SENSITIVE_KEY_SUFFIXES)


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, Mapping):
        return {
            key: (REDACTED if _is_sensitive_key(key) else _redact_value(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    return value


def redact_sensitive_data(
    logger: Any, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Scrub PII/secrets recursively without mutating the caller's payload.

    ``event`` is intentionally preserved as the operational event name. The
    processor runs before ``rename_event_to_message``, so a separate structured
    ``message`` field is still treated as patient content and removed.
    """
    return {
        key: (
            _redact_value(value)
            if key == "event"
            else REDACTED
            if _is_sensitive_key(key)
            else _redact_value(value)
        )
        for key, value in event_dict.items()
    }


def rename_event_to_message(
    logger: Any, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Rename structlog's 'event' field to 'message' for JSON compliance."""
    if "event" not in event_dict:
        return dict(event_dict)
    return {
        **{key: value for key, value in event_dict.items() if key != "event"},
        "message": event_dict["event"],
    }


def add_static_fields(
    logger: Any, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Inject service name and environment into every log line."""
    return {
        "service": "clinicai-api",
        "environment": os.environ.get("APP_ENV", "development"),
        **event_dict,
    }


def setup_logging() -> None:
    """Configure structlog and standard library logging for structured JSON output."""
    log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level_str, logging.INFO)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", key="timestamp"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        add_static_fields,
        redact_sensitive_data,
        rename_event_to_message,
    ]

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)

    # Intercept and route framework/Uvicorn loggers to standard logging propagation
    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"):
        log = logging.getLogger(logger_name)
        log.handlers = []
        log.propagate = True

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
