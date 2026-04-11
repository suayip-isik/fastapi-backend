"""API anahtarı repository modülü.

Bu modül, API anahtarlarının veritabanı işlemlerini yönetir.
Kullanıcıların API anahtarlarını oluşturma, sorgulama ve yönetme
işlemlerini gerçekleştirir.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import or_, select

from app.db.models.api_key import APIKey
from app.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    from uuid import UUID


class APIKeyRepository(BaseRepository[APIKey]):
    """API anahtarı veritabanı işlemlerini yöneten repository sınıfı.

    Bu sınıf, API anahtarlarının CRUD işlemlerini ve özel sorgulamalarını
    gerçekleştirir. BaseRepository'den miras alarak temel veritabanı
    işlemlerini sağlar.

    Attributes:
        model: İşlem yapılacak SQLAlchemy model sınıfı (APIKey).

    Example:
        >>> repo = APIKeyRepository(session)
        >>> keys = await repo.get_active_by_user(user_id)
    """

    model = APIKey

    async def get_active_by_user(self, user_id: UUID) -> list[APIKey]:
        """Belirtilen kullanıcıya ait aktif API anahtarlarını getirir.

        Kullanıcının tüm aktif (is_active=True) API anahtarlarını
        veritabanından sorgulayarak döndürür.

        Args:
            user_id: Kullanıcının benzersiz kimlik numarası (UUID).

        Returns:
            Kullanıcıya ait aktif APIKey nesnelerinin listesi.
            Aktif anahtar yoksa boş liste döner.

        Example:
            >>> keys = await repo.get_active_by_user(user.id)
            >>> for key in keys:
            ...     print(key.name)
        """
        result = await self._session.execute(
            select(APIKey).where(APIKey.user_id == user_id, APIKey.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def get_active_by_prefix(self, prefix: str) -> list[APIKey]:
        """Belirtilen prefix ile eşleşen aktif API anahtarlarını getirir.

        API anahtarı doğrulama sürecinin ilk adımında kullanılır.
        Prefix eşleşmesi yapıldıktan sonra hash doğrulaması ayrıca
        yapılmalıdır.

        Args:
            prefix: API anahtarının prefix kısmı (ilk N karakter).

        Returns:
            Prefix ile eşleşen aktif APIKey nesnelerinin listesi.
            Eşleşme yoksa boş liste döner.

        Note:
            Döndürülen anahtarların hash değerleri ayrıca doğrulanmalıdır.
            Bu metot yalnızca prefix filtrelemesi yapar.

        Example:
            >>> candidates = await repo.get_active_by_prefix("sk_live_abc")
            >>> for key in candidates:
            ...     if verify_hash(raw_key, key.key_hash):
            ...         return key
        """
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(APIKey).where(
                APIKey.key_prefix == prefix,
                APIKey.is_active.is_(True),
                or_(APIKey.expires_at.is_(None), APIKey.expires_at > now),
            )
        )
        return list(result.scalars().all())
