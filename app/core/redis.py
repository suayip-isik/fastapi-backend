"""
Async Redis client — e-posta doğrulama ve şifre sıfırlama token'ları için.
ARQ'nun kendi queue pool'undan bağımsız, doğrudan erişim sağlar.
"""

from __future__ import annotations

import redis.asyncio as aioredis

from app.core.config import settings

_redis_client: aioredis.Redis | None = None


async def get_redis_client() -> aioredis.Redis:
    """
    Singleton async Redis client döner.
    İlk çağrıda bağlantı havuzu oluşturulur, sonrakiler aynı instance'ı kullanır.
    Test'lerde _redis_client doğrudan fakeredis instance'ı ile override edilir.
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
    """Uygulama kapanışında lifespan tarafından çağrılır."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
