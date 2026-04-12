"""
Custom middleware'ler:
- LanguageMiddleware: Accept-Language header'dan dil algılar
- RequestIDMiddleware: Her isteğe UUID atar
- TimingMiddleware: İşlem süresini loglar
- SecurityHeadersMiddleware: Güvenlik header'ları ekler (/docs hariç)
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, language_var
from app.core.logging import get_logger, ip_address_var, request_id_var, user_agent_var

_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

logger = get_logger(__name__)


def _parse_accept_language(header: str) -> str:
    """Accept-Language header'ını parse eder, desteklenen ilk dili döndürür."""
    for part in header.replace(" ", "").split(","):
        lang = part.split(";")[0].split("-")[0].lower()
        if lang in SUPPORTED_LANGUAGES:
            return lang
    return DEFAULT_LANGUAGE


class LanguageMiddleware(BaseHTTPMiddleware):
    """Accept-Language header'dan dil algılar ve context var'a yazar.

    Örn: Accept-Language: tr-TR,tr;q=0.9,en;q=0.8 → language_var = "tr"
    Desteklenmeyen veya eksik header → DEFAULT_LANGUAGE ("en")
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        lang = _parse_accept_language(request.headers.get("Accept-Language", ""))
        token = language_var.set(lang)
        try:
            return await call_next(request)
        finally:
            language_var.reset(token)


# /docs, /redoc ve audience-specific schema docs için CSP gevşetilir
DOCS_PATHS = {"/docs", "/redoc", "/openapi.json"}

# HSTS sadece production'da anlamlı; diğer ortamlarda da eklenir ama tarayıcılar
# localhost için zaten görmezden gelir.
_HSTS_VALUE = "max-age=31536000; includeSubDomains"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Her HTTP request'e benzersiz X-Request-ID header ekler.

    Gelen request'te X-Request-ID varsa onu kullanır, yoksa yeni UUID
    oluşturur. Request ID context variable olarak saklanır ve tüm log
    kayıtlarına otomatik eklenir. Response header'ına da eklenir.
    Ayrıca IP adresi ve user-agent bilgilerini de context'e bind eder.

    Note:
        - Request ID structlog context'ine bind edilir
        - Client tarafından gönderilen ID'ler kabul edilir
        - UUID4 formatında oluşturulur
        - IP adresi ve user-agent da log context'ine eklenir

    Example:
        >>> # Request: GET /users (X-Request-ID yok)
        >>> # Response: 200 OK (X-Request-ID: abc-123-def)
        >>> # Logs: {"event": "...", "request_id": "abc-123-def"}
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Request'i işler ve request ID ekler.

        X-Request-ID header'ını kontrol eder; yoksa yeni UUID oluşturur.
        Request ID, IP adresi ve user-agent bilgilerini context variable'lara
        bind eder. Response işlendikten sonra context'i temizler.

        Args:
            request: Gelen HTTP request
            call_next: Sonraki middleware/handler fonksiyonu

        Returns:
            Response: X-Request-ID header'ı eklenmiş HTTP response
        """
        raw_rid = request.headers.get("X-Request-ID", "")
        request_id = raw_rid if _UUID4_RE.match(raw_rid) else str(uuid4())
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
    """Request işlem süresini ölçer ve loglar.

    Her HTTP request'in işlenme süresini milisaniye cinsinden hesaplar.
    Süre bilgisini X-Process-Time-Ms response header'ına ekler ve
    structlog ile detaylı request log kaydı oluşturur.

    Note:
        - time.perf_counter() ile yüksek hassasiyette ölçüm
        - Süre 2 ondalık basamağa yuvarlanır
        - Method, path, status code ve süre loglanır

    Example:
        >>> # Request: POST /auth/login (500ms sürer)
        >>> # Response: 200 OK (X-Process-Time-Ms: 500.23)
        >>> # Log: {"event": "request_completed", "duration_ms": 500.23}
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Request'i zamanlar ve süre bilgisini loglar.

        Request işleme başlamadan önce zamanı kaydeder, işlem bittikten
        sonra geçen süreyi hesaplar. Süreyi hem response header'ına ekler
        hem de log kaydı oluşturur.

        Args:
            request: Gelen HTTP request
            call_next: Sonraki middleware/handler fonksiyonu

        Returns:
            Response: X-Process-Time-Ms header'ı eklenmiş HTTP response
        """
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
    """Tüm HTTP response'lara güvenlik header'ları ekler.

    OWASP önerileri doğrultusunda güvenlik header'ları ekler:
    - Content-Security-Policy (CSP): XSS koruması
    - X-Content-Type-Options: MIME sniffing koruması
    - X-Frame-Options: Clickjacking koruması
    - HSTS: HTTPS zorunluluğu
    - CORS policy header'ları

    API documentation path'leri (/docs, /redoc, /schema/*) için
    CSP politikası gevşetilir (SwaggerUI/ReDoc için gerekli).

    Note:
        - /docs ve /redoc için unsafe-inline izni verilir
        - Production dışında HSTS tarayıcılar tarafından göz ardı edilir
        - Permissions-Policy ile tehlikeli API'lar engellenir

    Example:
        >>> # Normal endpoint: GET /users
        >>> # Response headers: X-Frame-Options: DENY, CSP: default-src 'self'
        >>> # Docs endpoint: GET /docs
        >>> # Response headers: CSP: script-src 'self' 'unsafe-inline' ...
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Request'i işler ve güvenlik header'larını ekler.

        Response oluşturulduktan sonra güvenlik header'larını ekler.
        Documentation endpoint'leri için CSP politikası gevşetilir,
        diğer endpoint'ler için sıkı güvenlik politikası uygulanır.

        Args:
            request: Gelen HTTP request
            call_next: Sonraki middleware/handler fonksiyonu

        Returns:
            Response: Güvenlik header'ları eklenmiş HTTP response
        """
        response = await call_next(request)

        # /docs, /redoc ve /schema/*/docs endpoint'leri için CSP'yi gevşet
        is_docs = request.url.path in DOCS_PATHS or request.url.path.startswith("/schema/")
        if is_docs:
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
        response.headers["Strict-Transport-Security"] = _HSTS_VALUE
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

        return response
