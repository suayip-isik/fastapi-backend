"""Permission provider testleri."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.adapters.infrastructure import RedisAdapter
from app.services.permissions import PermissionCache, PermissionProvider, PermissionQueryService


@pytest.mark.asyncio
async def test_permission_provider_returns_cached_permissions() -> None:
    user_id = uuid4()
    cache = AsyncMock(spec=PermissionCache)
    cache.get.return_value = {"users.list"}
    query_service = AsyncMock(spec=PermissionQueryService)
    provider = PermissionProvider(query_service=query_service, cache=cache)

    result = await provider.get_permissions(user_id)

    assert result == {"users.list"}
    query_service.get_permissions.assert_not_awaited()
    cache.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_permission_provider_populates_cache_on_miss() -> None:
    user_id = uuid4()
    cache = AsyncMock(spec=PermissionCache)
    cache.get.return_value = None
    query_service = AsyncMock(spec=PermissionQueryService)
    query_service.get_permissions.return_value = {"users.list", "users.update.profile"}
    provider = PermissionProvider(query_service=query_service, cache=cache)

    result = await provider.get_permissions(user_id)

    assert result == {"users.list", "users.update.profile"}
    query_service.get_permissions.assert_awaited_once_with(user_id)
    cache.set.assert_awaited_once_with(user_id, {"users.list", "users.update.profile"})


@pytest.mark.asyncio
async def test_permission_cache_invalid_json_is_dropped(fake_redis) -> None:
    user_id = uuid4()
    key = f"user_permissions:{user_id}"
    await fake_redis.set(key, "{bad-json")

    cache = PermissionCache(RedisAdapter())
    result = await cache.get(user_id)

    assert result is None
    assert await fake_redis.get(key) is None
