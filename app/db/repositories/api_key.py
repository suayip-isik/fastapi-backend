"""APIKey repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.db.models.api_key import APIKey
from app.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    from uuid import UUID


class APIKeyRepository(BaseRepository[APIKey]):
    model = APIKey

    async def get_active_by_user(self, user_id: UUID) -> list[APIKey]:
        result = await self._session.execute(
            select(APIKey).where(APIKey.user_id == user_id, APIKey.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def get_active_by_prefix(self, prefix: str) -> list[APIKey]:
        """Prefix eşleşen aktif key'leri döndür (sonra hash doğrulanır)."""
        result = await self._session.execute(
            select(APIKey).where(APIKey.key_prefix == prefix, APIKey.is_active.is_(True))
        )
        return list(result.scalars().all())
