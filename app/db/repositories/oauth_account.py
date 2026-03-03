"""OAuthAccount repository — provider bazlı sosyal hesap sorgular."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from app.db.models.oauth_account import OAuthAccount
from app.db.repositories.base import BaseRepository


class OAuthAccountRepository(BaseRepository[OAuthAccount]):
    model = OAuthAccount

    async def get_by_provider(self, provider: str, provider_user_id: str) -> OAuthAccount | None:
        result = await self._session.execute(
            select(OAuthAccount).where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_user_id == provider_user_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        user_id: UUID,
        provider: str,
        provider_user_id: str,
        email: str | None,
        access_token: str | None,
    ) -> OAuthAccount:
        """(provider, provider_user_id) çifti varsa güncelle, yoksa oluştur."""
        existing = await self.get_by_provider(provider, provider_user_id)
        if existing:
            return await self.update(existing.id, access_token=access_token)
        return await self.create(
            user_id=user_id,
            provider=provider,
            provider_user_id=provider_user_id,
            email=email,
            access_token=access_token,
        )
