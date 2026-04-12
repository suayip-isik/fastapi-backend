"""
CacheService — Redis tabanlı JSON cache yardımcısı.

Kullanım:
    await CacheService.set(key, data_dict, ttl=300)
    cached = await CacheService.get(key)  # dict | None
    await CacheService.delete(key1, key2)
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from app.adapters.infrastructure import RedisAdapter

if TYPE_CHECKING:
    from app.ports.infrastructure import RedisPort


class CacheService:
    """Redis tabanlı JSON cache servisi.

    Key-value cache operasyonları sağlar. Veriler JSON formatında
    serialize edilerek Redis'te saklanır.

    Note:
        Tüm metotlar statik olup, Redis client'ı her çağrıda
        connection pool'dan alınır.
    """

    def __init__(self, redis: RedisPort | None = None) -> None:
        self._redis = redis or RedisAdapter()

    async def get(self, key: str) -> dict[str, Any] | None:
        """Cache'den JSON değer okur.

        Args:
            key: Cache key

        Returns:
            Deserialize edilmiş dict veya key yoksa None
        """
        raw = await self._redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)  # type: ignore[no-any-return]

    async def set(self, key: str, value: dict[str, Any], ttl: int) -> None:
        """Cache'e JSON değer yazar.

        Değer JSON olarak serialize edilir. TTL süresi sonunda
        Redis tarafından otomatik silinir.

        Args:
            key: Cache key
            value: Saklanacak dict (JSON serializable olmalı)
            ttl: Time-to-live saniye cinsinden
        """
        await self._redis.setex(key, ttl, json.dumps(value, default=str))

    async def delete(self, *keys: str) -> None:
        """Cache'den bir veya daha fazla key siler.

        Var olmayan key'ler sessizce atlanır.

        Args:
            *keys: Silinecek cache key'leri
        """
        await self._redis.delete(*keys)

    async def set_str(self, key: str, value: str, ttl: int) -> None:
        """Cache'e ham string değer yazar (JSON encoding olmadan).

        Token, user_id gibi düz string değerleri saklamak için kullanılır.

        Args:
            key: Cache key
            value: Saklanacak ham string değer
            ttl: Time-to-live saniye cinsinden
        """
        await self._redis.setex(key, ttl, value)
