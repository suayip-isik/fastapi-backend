"""OAuthAccount repository — provider bazlı sosyal hesap sorgular."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.db.models.oauth_account import OAuthAccount
from app.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    from uuid import UUID


class OAuthAccountRepository(BaseRepository[OAuthAccount]):
    """OAuth sosyal hesap kayıtları için repository sınıfı.

    Google, GitHub gibi OAuth sağlayıcılarından gelen kullanıcı hesap
    bilgilerini yönetir. Her kullanıcının birden fazla OAuth hesabı
    olabilir (farklı sağlayıcılardan).

    Attributes:
        model: OAuthAccount SQLAlchemy modeli.

    Example:
        >>> repo = OAuthAccountRepository(session)
        >>> account = await repo.get_by_provider("google", "123456")
        >>> if account:
        ...     print(f"Kullanıcı: {account.user_id}")
    """

    model = OAuthAccount

    async def get_by_provider(self, provider: str, provider_user_id: str) -> OAuthAccount | None:
        """Sağlayıcı ve sağlayıcı kullanıcı ID'sine göre hesap getirir.

        Belirtilen OAuth sağlayıcısında (google, github vb.) kayıtlı
        kullanıcıyı benzersiz sağlayıcı ID'si ile arar.

        Args:
            provider: OAuth sağlayıcı adı (örn: "google", "github").
            provider_user_id: Sağlayıcıdaki benzersiz kullanıcı ID'si.

        Returns:
            Eşleşen OAuthAccount kaydı veya bulunamazsa None.

        Example:
            >>> account = await repo.get_by_provider("github", "12345678")
            >>> if account:
            ...     print(f"E-posta: {account.email}")
        """
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
        """OAuth hesabını günceller veya yeni kayıt oluşturur.

        (provider, provider_user_id) çifti mevcut ise access_token güncellenir,
        yoksa yeni OAuth hesabı kaydı oluşturulur.

        Args:
            user_id: İlişkili kullanıcının UUID'si.
            provider: OAuth sağlayıcı adı (örn: "google", "github").
            provider_user_id: Sağlayıcıdaki benzersiz kullanıcı ID'si.
            email: Sağlayıcıdan alınan e-posta adresi (opsiyonel).
            access_token: OAuth erişim token'ı (opsiyonel).

        Returns:
            Güncellenen veya yeni oluşturulan OAuthAccount kaydı.

        Example:
            >>> account = await repo.upsert(
            ...     user_id=user.id,
            ...     provider="google",
            ...     provider_user_id="118234567890",
            ...     email="user@gmail.com",
            ...     access_token="ya29.xxx",
            ... )
        """
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
