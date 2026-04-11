"""User repository — domain-specific sorgular."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import func, or_, select

if TYPE_CHECKING:
    from uuid import UUID

from app.core.permissions import USER_PERMISSIONS
from app.db.models.role import Role, RolePermission
from app.db.models.user import SurfaceType, User
from app.db.repositories.base import SoftDeleteRepository


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

    async def _get_default_role_id(self) -> UUID:
        result = await self._session.execute(
            select(Role)
            .where(Role.name == "user", Role.deleted_at.is_(None))
            .order_by(Role.is_system.desc(), Role.created_at.asc())
        )
        roles = result.scalars().all()
        if roles:
            return roles[0].id

        role = Role(name="user", description="User", is_system=True)
        self._session.add(role)
        await self._session.flush()
        for permission in USER_PERMISSIONS:
            self._session.add(RolePermission(role_id=role.id, permission=permission))
        await self._session.flush()
        return role.id

    async def create(self, **data: Any) -> User:
        if "role_id" not in data:
            data["role_id"] = await self._get_default_role_id()
        return await super().create(**data)

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

    async def get_by_pending_email(self, email: str) -> User | None:
        """Bekleyen e-posta adresine göre kullanıcı getirir."""
        result = await self._session.execute(
            select(User).where(
                User.pending_email == email.lower(),
                User.deleted_at.is_(None),
            )
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

    async def get_active_by_email(
        self,
        email: str,
        *,
        surface: SurfaceType | None = None,
    ) -> User | None:
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
        stmt = select(User).where(
            User.email == email.lower(),
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        if surface is not None:
            stmt = stmt.where(User.surface == surface.value)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_pending_email(self, email: str) -> User | None:
        """Aktif kullanıcıyı pending email adresine göre getirir."""
        result = await self._session.execute(
            select(User).where(
                User.pending_email == email.lower(),
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def email_exists(self, email: str, *, exclude_user_id: UUID | None = None) -> bool:
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
        normalized = email.lower()
        stmt = (
            select(func.count())
            .select_from(User)
            .where(
                or_(User.email == normalized, User.pending_email == normalized),
                User.deleted_at.is_(None),
            )
        )
        if exclude_user_id is not None:
            stmt = stmt.where(User.id != exclude_user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one() > 0

    async def count_stats(self) -> tuple[int, int, int]:
        stmt = select(
            func.count().filter(User.deleted_at.is_(None)).label("total"),
            func.count()
            .filter(User.is_active.is_(True), User.deleted_at.is_(None))
            .label("active"),
            func.count()
            .filter(User.is_active.is_(False), User.deleted_at.is_(None))
            .label("inactive"),
        )
        row = (await self._session.execute(stmt)).one()
        return row.active, row.inactive, row.total

    def _apply_filters(
        self,
        stmt: Any,
        *,
        q: str | None,
        role: str | None,
        is_active: bool | None,
        is_verified: bool | None,
    ) -> Any:
        if q is not None:
            pattern = f"%{q}%"
            stmt = stmt.where(
                or_(
                    User.email.ilike(pattern),
                    User.username.ilike(pattern),
                    User.full_name.ilike(pattern),
                )
            )
        if role is not None:
            stmt = stmt.where(
                User.role_id == select(Role.id).where(Role.name == role).scalar_subquery()
            )
        if is_active is not None:
            stmt = stmt.where(User.is_active.is_(is_active))
        if is_verified is not None:
            stmt = stmt.where(User.is_verified.is_(is_verified))
        return stmt

    async def search_page(
        self,
        *,
        q: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        is_verified: bool | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[User], int]:
        count_col = func.count().over().label("_total")
        stmt = (
            select(User, count_col)
            .where(User.deleted_at.is_(None))
            .order_by(User.created_at.desc())
        )
        stmt = self._apply_filters(
            stmt, q=q, role=role, is_active=is_active, is_verified=is_verified
        )
        stmt = stmt.offset(offset).limit(limit)
        rows = (await self._session.execute(stmt)).all()
        items = [row[0] for row in rows]
        total = rows[0][1] if rows else 0
        return items, total

    async def search_deleted_page(
        self,
        *,
        q: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        is_verified: bool | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[User], int]:
        count_col = func.count().over().label("_total")
        stmt = (
            select(User, count_col)
            .where(User.deleted_at.is_not(None))
            .order_by(User.deleted_at.desc())
        )
        stmt = self._apply_filters(
            stmt, q=q, role=role, is_active=is_active, is_verified=is_verified
        )
        stmt = stmt.offset(offset).limit(limit)
        rows = (await self._session.execute(stmt)).all()
        items = [row[0] for row in rows]
        total = rows[0][1] if rows else 0
        return items, total
