"""Default infrastructure adapter implementasyonları."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.redis import get_redis_client
from app.ports.infrastructure import RedisPort, StoragePort, TaskQueuePort, WebSocketNotifierPort
from app.storage.backends import StorageBackend, get_storage
from app.tasks.worker import enqueue

if TYPE_CHECKING:
    from fastapi import UploadFile


class RedisAdapter(RedisPort):
    """Global Redis client üstüne ince adapter."""

    async def get(self, key: str) -> str | None:
        redis = await get_redis_client()
        return await redis.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        redis = await get_redis_client()
        await redis.setex(key, ttl, value)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        redis = await get_redis_client()
        await redis.set(key, value, ex=ex)

    async def delete(self, *keys: str) -> None:
        redis = await get_redis_client()
        if keys:
            await redis.delete(*keys)

    async def exists(self, key: str) -> bool:
        redis = await get_redis_client()
        return bool(await redis.exists(key))

    async def sismember(self, key: str, member: str) -> bool:
        redis = await get_redis_client()
        return bool(await redis.sismember(key, member))

    async def srem(self, key: str, member: str) -> None:
        redis = await get_redis_client()
        await redis.srem(key, member)

    async def sadd(self, key: str, *members: str) -> None:
        redis = await get_redis_client()
        if members:
            await redis.sadd(key, *members)

    async def expire(self, key: str, ttl: int) -> None:
        redis = await get_redis_client()
        await redis.expire(key, ttl)

    async def ttl(self, key: str) -> int:
        redis = await get_redis_client()
        return int(await redis.ttl(key))

    async def scan(self, cursor: int, match: str, count: int) -> tuple[int, list[str]]:
        redis = await get_redis_client()
        next_cursor, keys = await redis.scan(cursor, match=match, count=count)
        return int(next_cursor), list(keys)

    async def ping(self) -> bool:
        redis = await get_redis_client()
        return bool(await redis.ping())


class ARQTaskQueueAdapter(TaskQueuePort):
    """ARQ queue helper adapter'ı."""

    async def enqueue(self, task_func: Any, *args: Any, **kwargs: Any) -> None:
        await enqueue(task_func, *args, **kwargs)


class WebSocketNotifierAdapter(WebSocketNotifierPort):
    """WebSocket manager üstüne notifier adapter'ı."""

    async def notify_user(self, user_id: str, payload: dict[str, object]) -> None:
        from app.websockets.manager import manager

        await manager.send_to_user_all_rooms(user_id, payload)


class StorageAdapter(StoragePort):
    """Storage backend adapter'ı."""

    def __init__(self, backend: StorageBackend | None = None) -> None:
        self._backend = backend or get_storage()

    async def upload(self, file: UploadFile, folder: str = "") -> str:
        return await self._backend.upload(file, folder=folder)

    async def delete(self, key: str) -> None:
        await self._backend.delete(key)

    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        return await self._backend.get_url(key, expires_in=expires_in)

    async def get_public_url(self, key: str) -> str:
        return await self._backend.get_public_url(key)
