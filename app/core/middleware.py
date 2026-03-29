"""
Custom middleware'ler:
- RequestIDMiddleware: Her isteğe UUID atar
- TimingMiddleware: İşlem süresini loglar
- SecurityHeadersMiddleware: Güvenlik header'ları ekler (/docs hariç)
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.logging import get_logger, ip_address_var, request_id_var, user_agent_var

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

logger = get_logger(__name__)

# /docs ve /redoc için CSP gevşetilir
DOCS_PATHS = {"/docs", "/redoc", "/openapi.json"}


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        rid_token = request_id_var.set(request_id)
        ip_token = ip_address_var.set(request.client.host if request.client else "-")
        ua_token = user_agent_var.set(request.headers.get("user-agent", "-"))
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(rid_token)
            ip_address_var.reset(ip_token)
            user_agent_var.reset(ua_token)


class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Process-Time-Ms"] = str(duration_ms)
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # /docs ve /redoc için CSP'yi gevşet
        if request.url.path in DOCS_PATHS:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://unpkg.com; "
                "style-src 'self' 'unsafe-inline' https://unpkg.com; "
                "img-src 'self' data: https://fastapi.tiangolo.com https://unpkg.com; "
                "font-src 'self' https://unpkg.com;"
            )
        else:
            response.headers["Content-Security-Policy"] = "default-src 'self'"

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        return response
