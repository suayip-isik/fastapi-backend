"""Runtime access policy helper'ları."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from starlette.requests import Request


class RuntimeAccessMode(StrEnum):
    """Operational runtime surfaces için erişim modları."""

    PUBLIC = "public"
    INTERNAL = "internal"
    DISABLED = "disabled"


DOCS_PATHS = frozenset(
    {
        "/docs",
        "/redoc",
        "/openapi.json",
        "/schema/admin/openapi.json",
        "/schema/client/openapi.json",
        "/schema/admin/docs",
        "/schema/client/docs",
    }
)
HEALTH_DETAIL_PATHS = frozenset({"/health", "/health/ready"})


def is_docs_path(path: str) -> bool:
    """Docs veya schema path'i mi?"""
    return path in DOCS_PATHS


def get_runtime_access_mode(path: str) -> RuntimeAccessMode | None:
    """Path için tanımlı runtime access mode'u döndür."""
    if is_docs_path(path):
        return RuntimeAccessMode(settings.DOCS_ACCESS_MODE)
    if path == "/metrics":
        return RuntimeAccessMode(settings.METRICS_ACCESS_MODE)
    if path in HEALTH_DETAIL_PATHS:
        return RuntimeAccessMode(settings.HEALTH_DETAIL_ACCESS_MODE)
    return None


def has_internal_access(request: Request) -> bool:
    """Internal access token header veya query param ile doğrulanır."""
    configured_token = settings.INTERNAL_ACCESS_TOKEN.strip()
    if not configured_token:
        return False

    supplied = request.headers.get("X-Internal-Access-Token", "").strip()
    if supplied and supplied == configured_token:
        return True

    query_supplied = request.query_params.get("access_token", "").strip()
    return bool(query_supplied and query_supplied == configured_token)


def should_enforce_runtime_access() -> bool:
    """Runtime access policies sadece production'da zorunlu tutulur."""
    return settings.is_production
