"""
Async Redis client — e-posta dogrulama ve sifre sifirlama token'lari icin.
ARQ'nun kendi queue pool'undan bagimsiz, dogrudan erisim saglar.
"""

from __future__ import annotations

import redis.asyncio as aioredis

from app.core.config import settings

_redis_client: aioredis.Redis[str] | None = None


async def get_redis_client() -> aioredis.Redis[str]:
    """
    Singleton async Redis client doner.
    Ilk cagirida baglanti havuzu olusturulur, sonrakiler ayni instance'i kullanir.
    Test'lerde _redis_client dogrudan fakeredis instance'i ile override edilir.
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
    """Uygulama kapanisinda lifespan tarafindan cagirilir."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()  # type: ignore[attr-defined]
        _redis_client = None
