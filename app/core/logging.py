"""
Structured logging — structlog + JSON format.
Request ID her log satirina otomatik eklenir.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import MutableMapping

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")
ip_address_var: ContextVar[str] = ContextVar("ip_address", default="-")
user_agent_var: ContextVar[str] = ContextVar("user_agent", default="-")


def _add_request_context(
    logger: Any, method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Her log kaydına request context bilgilerini ekler.

    Request ID ve user ID gibi context variables'dan alınan bilgileri
    log event dictionary'sine otomatik olarak ekler. Structlog processor
    pipeline'ında kullanılır.

    Args:
        logger: Logger instance (structlog tarafından sağlanır).
        method: Log metodu adı (info, error, vs.).
        event_dict: Log event verilerini içeren dictionary.

    Returns:
        Güncellenmiş event dictionary (request_id ve user_id eklenir).

    Note:
        Context variables (request_id_var, user_id_var) middleware
        tarafından her request için set edilir.
    """
    event_dict["request_id"] = request_id_var.get()
    event_dict["user_id"] = user_id_var.get()
    return event_dict


def setup_logging() -> None:
    """Structlog yapılandırmasını başlatır ve log formatını ayarlar.

    Settings'den alınan yapılandırmaya göre JSON veya console format kullanır.
    Log level APP_ENV ve LOG_LEVEL ayarlarına göre dinamik olarak belirlenir.
    Request context (request_id, user_id) her log kaydına otomatik eklenir.

    Processor Pipeline:
        1. Log seviyesine göre filtreleme
        2. Log level bilgisi ekleme (INFO, ERROR, vb.)
        3. Positional arguments formatlama
        4. ISO format timestamp ekleme (UTC)
        5. Request context bilgileri ekleme (request_id, user_id)
        6. Stack trace bilgisi ekleme
        7. Exception formatı dönüştürme
        8. JSON veya console renderer

    Note:
        - Uygulama başlangıcında bir kez çağrılmalı (main.py'de)
        - Context variables middleware tarafından her request için set edilir
        - Production'da LOG_FORMAT="json" önerilir
        - Development'ta console renderer okunabilirlik sağlar

    Example:
        >>> setup_logging()
        >>> logger = get_logger(__name__)
        >>> logger.info("user_created", user_id=123, email="test@example.com")
        # JSON: {"event": "user_created", "timestamp": "2024-01-15T10:30:00Z",
        #        "user_id": 123, "email": "test@example.com", "request_id": "..."}

    Raises:
        AttributeError: LOG_LEVEL geçersiz bir değerse (INFO, DEBUG, WARNING, ERROR, CRITICAL olmalı).
    """
    from app.core.config import settings

    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    renderer: structlog.processors.JSONRenderer | structlog.dev.ConsoleRenderer
    if settings.LOG_FORMAT == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            _add_request_context,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Yapılandırılmış logger instance döndürür.

    Structlog ile yapılandırılmış BoundLogger instance oluşturur.
    Logger instance request context bilgilerini otomatik olarak her
    log kaydına ekler.

    Args:
        name: Logger adı, genellikle modül adı (__name__).
              None ise root logger döner. Defaults to None.

    Returns:
        Yapılandırılmış structlog BoundLogger instance.

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("operation_completed", duration_ms=125)

        >>> # Service içinde kullanım
        >>> class UserService:
        ...     def __init__(self):
        ...         self.logger = get_logger(__name__)
        ...
        ...     def create_user(self, email: str):
        ...         self.logger.info("creating_user", email=email)

    Note:
        - setup_logging() önce çağrılmalı
        - Logger her modül için bir kez oluşturulup class attribute olarak saklanabilir
        - Context binding için bind() kullanılabilir: logger.bind(user_id=123)
    """
    return structlog.get_logger(name)  # type: ignore[no-any-return]
