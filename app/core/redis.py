"""
Async Redis client — e-posta dogrulama ve sifre sifirlama token'lari icin.
ARQ'nun kendi queue pool'undan bagimsiz, dogrudan erisim saglar.
"""

from __future__ import annotations

import redis.asyncio as aioredis

from app.core.config import settings

_redis_client: aioredis.Redis[str] | None = None


async def get_redis_client() -> aioredis.Redis[str]:
    """Global async Redis client instance döner.

    Singleton pattern ile tek bir Redis bağlantısı kullanılır.
    İlk çağrıda connection pool oluşturulur, sonraki çağrılarda
    aynı client döner. E-posta doğrulama token'ları, şifre sıfırlama
    token'ları ve diğer geçici veri saklama işlemleri için kullanılır.

    Returns:
        Redis client instance (aioredis, decode_responses=True).

    Note:
        - Connection pool otomatik yönetilir
        - decode_responses=True (string dönüşümü otomatik)
        - UTF-8 encoding varsayılan olarak kullanılır
        - Test'lerde _redis_client doğrudan fakeredis instance'i ile override edilir
        - ARQ'nun kendi queue pool'undan bağımsız çalışır

    Example:
        >>> redis = await get_redis_client()
        >>> await redis.set("email_token:abc123", "user@example.com", ex=3600)
        >>> email = await redis.get("email_token:abc123")
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """Redis bağlantısını kapatır ve kaynakları temizler.

    Global Redis client instance'ını kapatır ve None değerine atar.
    Uygulama kapanışında FastAPI lifespan context manager tarafından
    otomatik olarak çağrılır.

    Note:
        - Graceful shutdown sağlar
        - Connection pool'u düzgün şekilde kapatır
        - Client None değerine atanır (tekrar kullanımda yeni client oluşturulur)

    Example:
        >>> # app/main.py lifespan içinde
        >>> @asynccontextmanager
        >>> async def lifespan(app: FastAPI):
        ...     yield
        ...     await close_redis()
    """
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()  # type: ignore[attr-defined]
        _redis_client = None
