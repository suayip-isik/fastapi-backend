"""Infrastructure dependency factory'leri."""

from typing import Annotated

from fastapi import Depends

from app.adapters.infrastructure import (
    ARQTaskQueueAdapter,
    RedisAdapter,
    StorageAdapter,
    WebSocketNotifierAdapter,
)
from app.db.session_provider import get_default_session_factory
from app.ports.infrastructure import RedisPort, StoragePort, TaskQueuePort, WebSocketNotifierPort
from app.services.cache import CacheService
from app.services.permissions import PermissionCache, PermissionProvider, PermissionQueryService


def get_redis_port() -> RedisPort:
    return RedisAdapter()


def get_task_queue_port() -> TaskQueuePort:
    return ARQTaskQueueAdapter()


def get_storage_port() -> StoragePort:
    return StorageAdapter()


def get_websocket_notifier() -> WebSocketNotifierPort:
    return WebSocketNotifierAdapter()


def get_cache_service(
    redis: Annotated[RedisPort, Depends(get_redis_port)],
) -> CacheService:
    return CacheService(redis)


def get_permission_provider(
    redis: Annotated[RedisPort, Depends(get_redis_port)],
) -> PermissionProvider:
    return PermissionProvider(
        query_service=PermissionQueryService(get_default_session_factory()),
        cache=PermissionCache(redis),
    )


RedisPortDep = Annotated[RedisPort, Depends(get_redis_port)]
TaskQueuePortDep = Annotated[TaskQueuePort, Depends(get_task_queue_port)]
StoragePortDep = Annotated[StoragePort, Depends(get_storage_port)]
WebSocketNotifierDep = Annotated[WebSocketNotifierPort, Depends(get_websocket_notifier)]
CacheServiceDep = Annotated[CacheService, Depends(get_cache_service)]
PermissionProviderDep = Annotated[PermissionProvider, Depends(get_permission_provider)]
