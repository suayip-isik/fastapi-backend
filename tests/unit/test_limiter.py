"""Rate limiter yardımcıları için unit testler."""

from __future__ import annotations

import hashlib
import inspect
from collections.abc import Iterator
from uuid import uuid4

from fastapi.routing import APIRoute
from starlette.requests import Request

from app.api.v1.endpoints import users
from app.core.limiter import authenticated_user_or_ip_key
from app.core.security import TokenType
from app.main import app


def _request_with_headers(
    headers: dict[str, str],
    client: tuple[str, int] = ("203.0.113.10", 443),
) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/admin/users",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": client,
    }
    return Request(scope)


def _iter_admin_users_routes() -> Iterator[APIRoute]:
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == "/api/v1/admin/users":
            yield route


def test_authenticated_user_or_ip_key_uses_bearer_subject(monkeypatch) -> None:
    """Bearer access token varsa user id bazlı anahtar üretmeli."""
    user_id = str(uuid4())

    class _Payload:
        type = TokenType.ACCESS
        sub = user_id

    monkeypatch.setattr("app.core.limiter.decode_token", lambda token: _Payload())

    request = _request_with_headers({"Authorization": "Bearer test-token"})

    assert authenticated_user_or_ip_key(request) == f"user:{user_id}"


def test_authenticated_user_or_ip_key_hashes_api_key() -> None:
    """API key auth için ham key yerine hash bazlı anahtar kullanılmalı."""
    api_key = "sk_live_test_key"
    request = _request_with_headers({"X-API-Key": api_key})
    expected = hashlib.sha256(api_key.encode()).hexdigest()

    assert authenticated_user_or_ip_key(request) == f"api_key:{expected}"


def test_authenticated_user_or_ip_key_falls_back_to_ip() -> None:
    """Auth header yoksa IP fallback kullanılmalı."""
    request = _request_with_headers({})
    assert authenticated_user_or_ip_key(request) == "ip:203.0.113.10"


def test_create_admin_user_route_uses_dedicated_rate_limit() -> None:
    """Create admin route'u ayrılmış limit setting'ini kullanmalı."""
    route = next(route for route in _iter_admin_users_routes() if "POST" in route.methods)
    source = inspect.getsource(users.create_admin_user)

    assert route.endpoint is users.create_admin_user
    assert "RATE_LIMIT_ADMIN_USER_CREATE" in source
    assert "authenticated_user_or_ip_key" in source


def test_other_email_routes_still_use_shared_auth_email_limit() -> None:
    """Diğer email endpoint'leri mevcut ortak limit altında kalmalı."""
    assert "RATE_LIMIT_AUTH_EMAIL" in inspect.getsource(users.change_user_email)
    assert "RATE_LIMIT_AUTH_EMAIL" in inspect.getsource(users.resend_user_verification)
    assert "RATE_LIMIT_AUTH_EMAIL" in inspect.getsource(users.resend_admin_invite)
