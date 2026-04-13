"""Rate limiter singleton modülü.

Bu modül tüm endpoint'ler için kullanılan SlowAPI rate limiter instance'ını sağlar.
Redis backend ile IP-based rate limiting yapılandırması içerir.

Example:
    >>> from app.core.limiter import limiter
    >>>
    >>> @router.get("/endpoint")
    >>> @limiter.limit("10/minute")
    >>> async def my_endpoint():
    ...     return {"message": "Limited endpoint"}
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.exceptions import AuthenticationError, InvalidTokenError, TokenExpiredError
from app.core.security import TokenType, decode_token

if TYPE_CHECKING:
    from fastapi import Request


def authenticated_user_or_ip_key(request: Request) -> str:
    """Authenticated actor varsa onu, yoksa IP'yi rate limit anahtarı yap.

    Bearer token varsa user id, API key varsa hash'i kullanılır. Auth çözülemezse
    veya header yoksa IP bazlı fallback'e dönülür.
    """
    authorization = request.headers.get("Authorization", "").strip()
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            try:
                payload = decode_token(token)
            except (AuthenticationError, InvalidTokenError, TokenExpiredError):
                pass
            else:
                if payload.type is TokenType.ACCESS:
                    return f"user:{payload.sub}"

    api_key = request.headers.get("X-API-Key", "").strip()
    if api_key:
        digest = hashlib.sha256(api_key.encode()).hexdigest()
        return f"api_key:{digest}"

    return f"ip:{get_remote_address(request)}"


# Global rate limiter instance
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    enabled=settings.RATE_LIMIT_ENABLED,
)
"""SlowAPI rate limiter singleton instance.

Redis backend ile IP-based rate limiting sağlar. Limitlere ulaşıldığında
429 Too Many Requests HTTP hatası döner. Limit bilgileri Settings'den alınır.

Attributes:
    key_func: IP adresi çıkarma fonksiyonu (X-Forwarded-For destekli)
    storage_uri: Redis bağlantı URI'si (rate limit verilerinin saklandığı yer)
    default_limits: Tüm endpoint'lere uygulanan varsayılan limitler

Note:
    - Redis bağlantı hatası durumunda rate limiting bypass edilir
    - Response header'larında X-RateLimit-* bilgileri döner
    - IP-based tracking (get_remote_address ile X-Forwarded-For desteği)
    - Endpoint bazında özel limitler @limiter.limit() decorator ile ayarlanır

Example:
    Endpoint'e özel limit tanımlama:
        >>> @router.post("/login")
        >>> @limiter.limit("5/minute")
        >>> async def login():
        ...     pass

    Birden fazla limit tanımlama:
        >>> @router.post("/api/heavy")
        >>> @limiter.limit("10/minute;100/hour")
        >>> async def heavy_endpoint():
        ...     pass
"""
