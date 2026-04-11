"""Permission çözümleme servisleri."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.core.logging import get_logger
from app.db.models.role import RolePermission
from app.db.models.user import User as UserModel
from app.db.session_provider import AsyncSessionFactoryProtocol, session_scope
from app.services._keys import USER_PERMISSIONS_KEY, USER_PERMISSIONS_TTL

if TYPE_CHECKING:
    from uuid import UUID

    from app.ports.infrastructure import RedisPort

logger = get_logger(__name__)


class PermissionCache:
    """Permission cache erişimini kapsüller."""

    def __init__(self, redis: RedisPort) -> None:
        self._redis = redis

    async def get(self, user_id: UUID) -> set[str] | None:
        cached = await self._redis.get(USER_PERMISSIONS_KEY.format(str(user_id)))
        if not cached:
            return None
        try:
            return set(json.loads(cached))
        except json.JSONDecodeError:
            logger.warning("permission_cache_decode_failed", user_id=str(user_id))
            await self._redis.delete(USER_PERMISSIONS_KEY.format(str(user_id)))
            return None

    async def set(self, user_id: UUID, permissions: set[str]) -> None:
        await self._redis.set(
            USER_PERMISSIONS_KEY.format(str(user_id)),
            json.dumps(sorted(permissions)),
            ex=USER_PERMISSIONS_TTL,
        )


class PermissionQueryService:
    """Permission setini veritabanından yükler."""

    def __init__(self, session_factory: AsyncSessionFactoryProtocol) -> None:
        self._session_factory = session_factory

    async def get_permissions(self, user_id: UUID) -> set[str]:
        async with session_scope(self._session_factory) as session:
            result = await session.execute(
                select(RolePermission.permission)
                .join(UserModel, UserModel.role_id == RolePermission.role_id)
                .where(UserModel.id == user_id)
            )
            return set(result.scalars().all())


class PermissionProvider:
    """Cache ve query akışını orkestre eder."""

    def __init__(
        self,
        *,
        query_service: PermissionQueryService,
        cache: PermissionCache,
    ) -> None:
        self._query_service = query_service
        self._cache = cache

    async def get_permissions(self, user_id: UUID) -> set[str]:
        cached = await self._cache.get(user_id)
        if cached is not None:
            return cached

        permissions = await self._query_service.get_permissions(user_id)
        await self._cache.set(user_id, permissions)
        return permissions
