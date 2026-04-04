"""User repository — domain-specific sorgular."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.db.models.user import User
from app.db.repositories.base import SoftDeleteRepository

if TYPE_CHECKING:
    from uuid import UUID


class UserRepository(SoftDeleteRepository[User]):
    """User modeli için repository.

    User CRUD operasyonları ve özel sorguları sağlar. Soft delete
    destekler (SoftDeleteRepository'den inherit).

    Attributes:
        model: User SQLAlchemy modeli.

    Note:
        - Soft delete: deleted_at ile işaretleme
        - Default list() soft-deleted kayıtları exclude eder
        - Email sorguları case-insensitive çalışır
    """

    model = User

    async def get_by_email(self, email: str) -> User | None:
        """Email adresine göre kullanıcı getirir.

        Email adresi lowercase'e dönüştürülerek aranır. Soft-deleted
        kullanıcılar sonuçlara dahil edilmez.

        Args:
            email: Aranacak email adresi (case-insensitive).

        Returns:
            Bulunan User instance veya None.

        Example:
            >>> user = await repo.get_by_email("Test@Example.com")
            >>> if user:
            ...     print(user.username)
        """
        result = await self._session.execute(
            select(User).where(User.email == email.lower(), User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """Username'e göre kullanıcı getirir.

        Soft-deleted kullanıcılar sonuçlara dahil edilmez.

        Args:
            username: Aranacak kullanıcı adı (case-sensitive).

        Returns:
            Bulunan User instance veya None.

        Example:
            >>> user = await repo.get_by_username("johndoe")
        """
        result = await self._session.execute(
            select(User).where(User.username == username, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_with_oauth(self, user_id: UUID) -> User | None:
        """Kullanıcıyı OAuth hesaplarıyla birlikte getirir.

        OAuth hesapları eager load edilir (N+1 query problemi önlenir).
        Soft-deleted kullanıcılar sonuçlara dahil edilmez.

        Args:
            user_id: Kullanıcının UUID'si.

        Returns:
            OAuth hesapları yüklenmiş User instance veya None.

        Example:
            >>> user = await repo.get_with_oauth(user_id)
            >>> for oauth in user.oauth_accounts:
            ...     print(oauth.provider)
        """
        result = await self._session.execute(
            select(User)
            .options(selectinload(User.oauth_accounts))
            .where(User.id == user_id, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_active_by_email(self, email: str) -> User | None:
        """Aktif kullanıcıyı email adresine göre getirir.

        Hem is_active=True hem de soft-deleted olmayan kullanıcıları filtreler.
        Login işlemlerinde kullanılır.

        Args:
            email: Aranacak email adresi (case-insensitive).

        Returns:
            Aktif User instance veya None.

        Example:
            >>> user = await repo.get_active_by_email("active@example.com")
            >>> if user:
            ...     # Login işlemine devam et
            ...     pass
        """
        result = await self._session.execute(
            select(User).where(
                User.email == email.lower(),
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        """Email adresinin kayıtlı olup olmadığını kontrol eder.

        Kayıt sırasında duplicate email kontrolü için kullanılır.
        Soft-deleted kullanıcılar kontrole dahil edilmez.

        Args:
            email: Kontrol edilecek email adresi (case-insensitive).

        Returns:
            True eğer email kayıtlıysa, False değilse.

        Example:
            >>> if await repo.email_exists("new@example.com"):
            ...     raise ValueError("Email zaten kullanımda")
        """
        result = await self._session.execute(
            select(func.count())
            .select_from(User)
            .where(User.email == email.lower(), User.deleted_at.is_(None))
        )
        return result.scalar_one() > 0

    async def get_deleted_page(self, *, offset: int = 0, limit: int = 20) -> tuple[list[User], int]:
        """Soft-deleted kullanıcıları sayfalanmış olarak getirir.

        Admin trash view için kullanılır. Sadece deleted_at != None olan
        kayıtları döndürür. Window function ile toplam sayıyı da hesaplar.

        Args:
            offset: Atlanacak kayıt sayısı (varsayılan: 0).
            limit: Maksimum döndürülecek kayıt sayısı (varsayılan: 20).

        Returns:
            Tuple içinde:
                - list[User]: Silinen kullanıcı listesi.
                - int: Toplam silinen kullanıcı sayısı.

        Example:
            >>> users, total = await repo.get_deleted_page(offset=0, limit=10)
            >>> print(f"{len(users)} / {total} silinen kullanıcı")
        """
        count_col = func.count().over().label("_total")
        stmt = (
            select(User, count_col).where(User.deleted_at.is_not(None)).offset(offset).limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        items = [row[0] for row in rows]
        total = rows[0][1] if rows else 0
        return items, total
