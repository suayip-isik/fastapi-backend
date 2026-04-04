"""
UserService — kullanıcı yönetimi business logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.exceptions import AlreadyExistsError, BusinessRuleError, UserNotFoundError
from app.core.security import hash_password
from app.db.models.audit_log import AuditAction
from app.db.repositories.user import UserRepository
from app.services._keys import USER_CACHE_KEY, USER_CACHE_TTL, USER_EMAIL_CACHE_KEY
from app.services.base import AuditableMixin
from app.services.cache import CacheService

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.user import User, UserRole
    from app.schemas.user import UpdateUserRequest, UserResponse
    from app.services.audit import AuditService


class UserService(AuditableMixin):
    """Kullanıcı yönetimi iş mantığı servisi.

    Bu servis, kullanıcı CRUD işlemleri, aktivasyon/deaktivasyon,
    rol değişiklikleri ve soft-delete operasyonlarını yönetir.
    Tüm değişiklikler audit log'a kaydedilir ve cache invalidate edilir.

    Attributes:
        _repo: Kullanıcı veritabanı repository'si.
        _audit: Audit log servisi (opsiyonel).
    """

    def __init__(self, session: AsyncSession, audit: AuditService | None = None) -> None:
        """UserService'i başlatır.

        Args:
            session: Async SQLAlchemy veritabanı oturumu.
            audit: Audit log servisi. None ise audit logları atlanır.
        """
        self._repo = UserRepository(session)
        self._audit = audit

    async def get_by_id(self, user_id: UUID) -> User:
        """Belirtilen ID'ye sahip kullanıcıyı getirir.

        Args:
            user_id: Kullanıcının benzersiz tanımlayıcısı (UUID).

        Returns:
            Bulunan kullanıcı nesnesi.

        Raises:
            UserNotFoundError: Kullanıcı bulunamadığında.
        """
        user = await self._repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError()
        return user

    async def get_by_id_cached(self, user_id: UUID) -> UserResponse:
        """Cache destekli kullanıcı sorgulama.

        Önce Redis cache'i kontrol eder, yoksa veritabanından çeker
        ve cache'e yazar. Sadece read-only görüntüleme için uygundur.

        Args:
            user_id: Kullanıcının benzersiz tanımlayıcısı (UUID).

        Returns:
            Kullanıcı bilgilerini içeren UserResponse şeması.

        Raises:
            UserNotFoundError: Kullanıcı bulunamadığında.

        Note:
            Cache TTL süresi USER_CACHE_TTL sabiti ile belirlenir.
        """
        from app.schemas.user import UserResponse as _UserResponse

        key = USER_CACHE_KEY.format(str(user_id))
        cached = await CacheService.get(key)
        if cached:
            return _UserResponse.model_validate(cached)
        user = await self._repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError()
        schema = _UserResponse.model_validate(user)
        await CacheService.set(key, schema.model_dump(), USER_CACHE_TTL)
        return schema

    async def _invalidate_user_cache(self, user_id: UUID, email: str | None = None) -> None:
        """Kullanıcıya ait cache kayıtlarını temizler.

        Args:
            user_id: Kullanıcının benzersiz tanımlayıcısı.
            email: Kullanıcının e-posta adresi. Verilirse e-posta
                bazlı cache de temizlenir.
        """
        keys = [USER_CACHE_KEY.format(str(user_id))]
        if email:
            keys.append(USER_EMAIL_CACHE_KEY.format(email))
        await CacheService.delete(*keys)

    async def get_all(self, page: int = 1, size: int = 20) -> tuple[list[User], int]:
        """Tüm kullanıcıları sayfalanmış şekilde listeler.

        Args:
            page: Sayfa numarası (1'den başlar). Varsayılan: 1.
            size: Sayfa başına kayıt sayısı. Varsayılan: 20.

        Returns:
            İki elemanlı tuple:
                - Kullanıcı listesi (User nesneleri).
                - Toplam kullanıcı sayısı (pagination için).
        """
        return await self._repo.get_page(offset=(page - 1) * size, limit=size)

    async def update(self, user_id: UUID, data: UpdateUserRequest) -> User:
        """Kullanıcı bilgilerini günceller.

        E-posta değişikliğinde benzersizlik kontrolü yapar.
        Şifre güncellemesinde otomatik hash'leme uygular.
        Her güncelleme audit log'a kaydedilir.

        Args:
            user_id: Güncellenecek kullanıcının UUID'si.
            data: Güncellenecek alanları içeren request şeması.
                Sadece set edilmiş alanlar güncellenir.

        Returns:
            Güncellenmiş kullanıcı nesnesi.

        Raises:
            UserNotFoundError: Kullanıcı bulunamadığında.
            AlreadyExistsError: Yeni e-posta adresi başka bir
                kullanıcı tarafından kullanılıyorsa.
        """
        user = await self._repo.get_by_id_or_raise(user_id)

        update_data = data.model_dump(exclude_unset=True)

        if (
            "email" in update_data
            and update_data["email"] != user.email
            and await self._repo.email_exists(update_data["email"])
        ):
            raise AlreadyExistsError("Bu e-posta adresi zaten kullanılıyor.")

        if "password" in update_data:
            update_data["hashed_password"] = hash_password(update_data.pop("password"))

        await self._invalidate_user_cache(user_id, user.email)
        updated = await self._repo.update(user_id, **update_data)
        await self._audit_log(AuditAction.PROFILE_UPDATED, user_id=user_id)
        return updated

    async def deactivate(self, user_id: UUID) -> User:
        """Kullanıcı hesabını deaktive eder.

        Deaktive edilen kullanıcı sisteme giriş yapamaz ancak
        verileri korunur. İşlem audit log'a kaydedilir.

        Args:
            user_id: Deaktive edilecek kullanıcının UUID'si.

        Returns:
            Güncellenmiş (deaktif) kullanıcı nesnesi.

        Raises:
            UserNotFoundError: Kullanıcı bulunamadığında.
        """
        user = await self._repo.get_by_id_or_raise(user_id)
        await self._invalidate_user_cache(user_id, user.email)
        updated = await self._repo.update(user_id, is_active=False)
        await self._audit_log(AuditAction.USER_DEACTIVATED, user_id=user_id)
        return updated

    async def activate(self, user_id: UUID) -> User:
        """Deaktif kullanıcı hesabını yeniden aktifleştirir.

        Aktifleştirilen kullanıcı sisteme tekrar giriş yapabilir.
        İşlem audit log'a kaydedilir.

        Args:
            user_id: Aktifleştirilecek kullanıcının UUID'si.

        Returns:
            Güncellenmiş (aktif) kullanıcı nesnesi.

        Raises:
            UserNotFoundError: Kullanıcı bulunamadığında.
        """
        user = await self._repo.get_by_id_or_raise(user_id)
        await self._invalidate_user_cache(user_id, user.email)
        updated = await self._repo.update(user_id, is_active=True)
        await self._audit_log(AuditAction.USER_ACTIVATED, user_id=user_id)
        return updated

    async def change_role(self, user_id: UUID, role: UserRole) -> User:
        """Kullanıcının rolünü değiştirir.

        Rol değişikliği audit log'a eski ve yeni rol bilgisiyle
        birlikte kaydedilir. Bu işlem genellikle admin yetkisi gerektirir.

        Args:
            user_id: Rolü değiştirilecek kullanıcının UUID'si.
            role: Atanacak yeni rol (UserRole enum değeri).

        Returns:
            Güncellenmiş kullanıcı nesnesi.

        Raises:
            UserNotFoundError: Kullanıcı bulunamadığında.

        Example:
            >>> await user_service.change_role(user_id, UserRole.ADMIN)
        """
        current = await self._repo.get_by_id_or_raise(user_id)
        await self._invalidate_user_cache(user_id, current.email)
        updated = await self._repo.update(user_id, role=role)
        await self._audit_log(
            AuditAction.ROLE_CHANGED,
            user_id=user_id,
            extra={"old_role": current.role.value, "new_role": role.value},
        )
        return updated

    async def soft_delete(self, user_id: UUID) -> None:
        """Kullanıcıyı soft-delete ile siler.

        Kullanıcı veritabanından fiziksel olarak silinmez, sadece
        is_deleted bayrağı True yapılır. Bu sayede restore() ile
        geri getirilebilir. İşlem audit log'a kaydedilir.

        Args:
            user_id: Silinecek kullanıcının UUID'si.

        Raises:
            UserNotFoundError: Kullanıcı bulunamadığında.
            BusinessRuleError: Kullanıcı zaten silinmişse.
        """
        user = await self._repo.get_by_id_or_raise(user_id)
        if user.is_deleted:
            raise BusinessRuleError("Kullanıcı zaten silinmiş.")
        await self._invalidate_user_cache(user_id, user.email)
        await self._repo.soft_delete(user_id)
        await self._audit_log(AuditAction.USER_DELETED, user_id=user_id)

    async def restore(self, user_id: UUID) -> User:
        """Soft-delete ile silinmiş kullanıcıyı geri yükler.

        is_deleted bayrağı False yapılarak kullanıcı tekrar aktif
        hale getirilir. İşlem audit log'a kaydedilir.

        Args:
            user_id: Geri yüklenecek kullanıcının UUID'si.

        Returns:
            Geri yüklenmiş kullanıcı nesnesi.

        Raises:
            UserNotFoundError: Kullanıcı bulunamadığında
                (silinmiş kayıtlar dahil).
            BusinessRuleError: Kullanıcı zaten aktifse
                (silinmemiş durumdaysa).
        """
        user = await self._repo.get_by_id(user_id, include_deleted=True)
        if not user:
            raise UserNotFoundError()
        if not user.is_deleted:
            raise BusinessRuleError("Kullanıcı silinmemiş.")
        await self._invalidate_user_cache(user_id, user.email)
        restored = await self._repo.restore(user_id)
        await self._audit_log(AuditAction.USER_RESTORED, user_id=user_id)
        return restored
