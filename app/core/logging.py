"""
Structured logging — structlog + JSON format.
Request ID her log satırına otomatik eklenir.
"""
from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

import structlog
from structlog.types import EventDict, WrappedLogger

from app.core.config import settings

# ContextVar ile request-scoped değerler
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")


def _add_request_context(logger: WrappedLogger, method: str, event_dict: EventDict) -> EventDict:
    """Her log satırına request_id ve user_id ekle."""
    event_dict["request_id"] = request_id_var.get()
    event_dict["user_id"] = user_id_var.get()
    return event_dict


def setup_logging() -> None:
    """Uygulama başlangıcında bir kez çağrılır."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _add_request_context,
    ]

    if settings.LOG_FORMAT == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Standard library logging'i de structlog'a yönlendir
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Module-level logger al."""
    return structlog.get_logger(name)
