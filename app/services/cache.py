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
    @staticmethod
    async def get(key: str) -> dict[str, Any] | None:
        redis = await get_redis_client()
        raw = await redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)  # type: ignore[no-any-return]

    @staticmethod
    async def set(key: str, value: dict[str, Any], ttl: int) -> None:
        redis = await get_redis_client()
        await redis.setex(key, ttl, json.dumps(value, default=str))

    @staticmethod
    async def delete(*keys: str) -> None:
        redis = await get_redis_client()
        if keys:
            await redis.delete(*keys)
