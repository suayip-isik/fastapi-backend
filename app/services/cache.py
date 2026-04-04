"""
CacheService — Redis tabanlı JSON cache yardımcısı.

Kullanım:
    await CacheService.set(key, data_dict, ttl=300)
    cached = await CacheService.get(key)  # dict | None
    await CacheService.delete(key1, key2)
"""

from __future__ import annotations

import json
from typing import Any

from app.core.redis import get_redis_client


class CacheService:
    """Redis tabanlı JSON cache servisi.

    Key-value cache operasyonları sağlar. Veriler JSON formatında
    serialize edilerek Redis'te saklanır.

    Note:
        Tüm metotlar statik olup, Redis client'ı her çağrıda
        connection pool'dan alınır.
    """

    @staticmethod
    async def get(key: str) -> dict[str, Any] | None:
        """Cache'den JSON değer okur.

        Args:
            key: Cache key

        Returns:
            Deserialize edilmiş dict veya key yoksa None
        """
        redis = await get_redis_client()
        raw = await redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)  # type: ignore[no-any-return]

    @staticmethod
    async def set(key: str, value: dict[str, Any], ttl: int) -> None:
        """Cache'e JSON değer yazar.

        Değer JSON olarak serialize edilir. TTL süresi sonunda
        Redis tarafından otomatik silinir.

        Args:
            key: Cache key
            value: Saklanacak dict (JSON serializable olmalı)
            ttl: Time-to-live saniye cinsinden
        """
        redis = await get_redis_client()
        await redis.setex(key, ttl, json.dumps(value, default=str))

    @staticmethod
    async def delete(*keys: str) -> None:
        """Cache'den bir veya daha fazla key siler.

        Var olmayan key'ler sessizce atlanır.

        Args:
            *keys: Silinecek cache key'leri
        """
        redis = await get_redis_client()
        if keys:
            await redis.delete(*keys)
