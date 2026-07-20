"""Structured logging configuration for ClinicAI."""

import logging
import os
import sys
from typing import Any, Dict

import structlog


def rename_event_to_message(
    logger: Any, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Rename structlog's 'event' field to 'message' for JSON compliance."""
    if "event" in event_dict:
        event_dict["message"] = event_dict.pop("event")
    return event_dict


def setup_logging() -> None:
    """Configure structlog and standard library logging for structured JSON output."""
    log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level_str, logging.INFO)

    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", key="timestamp"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
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
