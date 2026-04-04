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

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# Global rate limiter instance
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
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
