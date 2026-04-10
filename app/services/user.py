"""
UserService — kullanıcı yönetimi business logic.
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from app.adapters.infrastructure import ARQTaskQueueAdapter, RedisAdapter
from app.core.config import settings
from app.core.exceptions import (
    AlreadyExistsError,
    BusinessRuleError,
    NotFoundError,
    UserNotFoundError,
)
from app.core.i18n import language_var
from app.core.permissions import Permission
from app.core.security import hash_password
from app.db.models.audit_log import AuditAction
from app.db.models.user import AccountType
from app.db.repositories.role import RoleRepository
from app.db.repositories.user import UserRepository
from app.ports.infrastructure import RedisPort, TaskQueuePort
from app.services._keys import (
    PASSWORD_RESET_KEY,
    USER_CACHE_KEY,
    USER_CACHE_TTL,
    USER_EMAIL_CACHE_KEY,
    USER_PERMISSIONS_KEY,
)
from app.services.base import AuditableMixin
from app.services.cache import CacheService
from app.tasks.worker import send_admin_invite_email

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.user import User
    from app.schemas.user import (
        CreateAdminUserRequest,
        UpdateUserRequest,
        UserResponse,
        UserStatsResponse,
    )
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

    def __init__(
        self,
        session: AsyncSession,
        audit: AuditService | None = None,
        *,
        cache: CacheService | None = None,
        redis: RedisPort | None = None,
        task_queue: TaskQueuePort | None = None,
    ) -> None:
        """UserService'i başlatır.

        Args:
            session: Async SQLAlchemy veritabanı oturumu.
            audit: Audit log servisi. None ise audit logları atlanır.
        """
        self._repo = UserRepository(session)
        self._role_repo = RoleRepository(session)
        self._audit = audit
        self._cache = cache or CacheService()
        self._redis = redis or RedisAdapter()
        self._task_queue = task_queue or ARQTaskQueueAdapter()

    async def _issue_admin_invite(self, user: User) -> None:
        token = secrets.token_urlsafe(32)
        await self._redis.setex(
            PASSWORD_RESET_KEY.format(token), settings.PASSWORD_RESET_TTL, str(user.id)
        )
        await self._task_queue.enqueue(
            send_admin_invite_email,
            user.email,
            token,
            language_var.get(),
        )

    async def _get_admin_role_or_raise(self, role_name: str):
        role = await self._role_repo.get_by_name(role_name)
        if not role:
            raise NotFoundError(f"'{role_name}' adında bir rol bulunamadı.")
        if Permission.ADMIN_PANEL_ACCESS.value not in role.permission_set:
            raise BusinessRuleError("Admin kullanıcıya yalnızca panel erişimi olan rol atanabilir.")
        return role

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
        cached = await self._cache.get(key)
        if cached:
            return _UserResponse.model_validate(cached)
        user = await self._repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError()
        schema = _UserResponse.model_validate(user)
        await self._cache.set(key, schema.model_dump(), USER_CACHE_TTL)
        return schema

    async def _invalidate_user_cache(
        self, user_id: UUID, email: str | None = None, invalidate_permissions: bool = False
    ) -> None:
        """Kullanıcıya ait cache kayıtlarını temizler.

        Args:
            user_id: Kullanıcının benzersiz tanımlayıcısı.
            email: Kullanıcının e-posta adresi. Verilirse e-posta cache de temizlenir.
            invalidate_permissions: True ise permission cache de temizlenir.
                Rol değişikliği sonrası True geçilmelidir.
        """
        keys = [USER_CACHE_KEY.format(str(user_id))]
        if email:
            keys.append(USER_EMAIL_CACHE_KEY.format(email))
        if invalidate_permissions:
            keys.append(USER_PERMISSIONS_KEY.format(str(user_id)))
        await self._cache.delete(*keys)

    async def get_stats(self) -> UserStatsResponse:
        """Sistemdeki kullanıcı istatistiklerini döndürür.

        Tek veritabanı sorgusuyla aktif, pasif ve toplam kullanıcı
        sayılarını hesaplar. Soft-delete ile silinmiş kullanıcılar
        sayımlara dahil edilmez.

        Returns:
            Aktif, pasif ve toplam kullanıcı sayılarını içeren şema.
        """
        from app.schemas.user import UserStatsResponse as _UserStatsResponse

        active, inactive, total = await self._repo.count_stats()
        return _UserStatsResponse(total=total, active=active, inactive=inactive)

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

    async def search(
        self,
        *,
        page: int = 1,
        size: int = 20,
        q: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        is_verified: bool | None = None,
    ) -> tuple[list[User], int]:
        """Filtrelere göre aktif kullanıcıları sayfalanmış şekilde arar.

        Arama terimi email, kullanıcı adı ve tam ad alanlarında ILIKE ile
        eşleştirilir. Filtreler opsiyoneldir; hiçbiri verilmezse tüm aktif
        kullanıcıları döndürür.

        Args:
            page: Sayfa numarası (1'den başlar).
            size: Sayfa başına kayıt sayısı.
            q: Serbest metin arama terimi.
            role: Rol filtresi.
            is_active: Aktiflik durumu filtresi.
            is_verified: Doğrulama durumu filtresi.

        Returns:
            (users, total) tuple.
        """
        return await self._repo.search_page(
            q=q,
            role=role,
            is_active=is_active,
            is_verified=is_verified,
            offset=(page - 1) * size,
            limit=size,
        )

    async def search_deleted(
        self,
        *,
        page: int = 1,
        size: int = 20,
        q: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        is_verified: bool | None = None,
    ) -> tuple[list[User], int]:
        """Soft-delete ile silinmiş kullanıcıları sayfalanmış şekilde arar.

        Silinme zamanına göre azalan sırada döner (en son silinen önce).
        Filtreler opsiyoneldir.

        Args:
            page: Sayfa numarası (1'den başlar).
            size: Sayfa başına kayıt sayısı.
            q: Serbest metin arama terimi.
            role: Rol filtresi.
            is_active: Silinmeden önceki aktiflik durumu filtresi.
            is_verified: Doğrulama durumu filtresi.

        Returns:
            (users, total) tuple.
        """
        return await self._repo.search_deleted_page(
            q=q,
            role=role,
            is_active=is_active,
            is_verified=is_verified,
            offset=(page - 1) * size,
            limit=size,
        )

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

    async def create_admin_user(self, data: CreateAdminUserRequest) -> User:
        """Yeni bir admin kullanıcı oluşturur ve davet e-postası gönderir."""
        email = data.email.lower()
        if await self._repo.email_exists(email):
            raise AlreadyExistsError("Bu e-posta adresi zaten kullanılıyor.")

        if data.username and await self._repo.get_by_username(data.username):
            raise AlreadyExistsError("Bu kullanıcı adı zaten kullanılıyor.")

        role = await self._get_admin_role_or_raise(data.role_name)
        user = await self._repo.create(
            email=email,
            username=data.username,
            full_name=data.full_name,
            role_id=role.id,
            account_type=AccountType.ADMIN.value,
            is_active=True,
            is_verified=False,
            hashed_password=None,
        )
        await self._issue_admin_invite(user)
        await self._audit_log(
            AuditAction.ADMIN_USER_CREATED,
            user_id=user.id,
            extra={"email": user.email, "role_name": role.name},
        )
        return user

    async def resend_admin_invite(self, user_id: UUID) -> User:
        """Şifresi henüz belirlenmemiş admin kullanıcıya daveti yeniden gönderir."""
        user = await self._repo.get_by_id_or_raise(user_id)
        if user.account_type != AccountType.ADMIN.value:
            raise BusinessRuleError("Yalnızca admin tipindeki kullanıcılar için davet gönderilebilir.")
        if user.hashed_password:
            raise BusinessRuleError("Şifresi belirlenmiş admin kullanıcıya davet yeniden gönderilemez.")

        await self._issue_admin_invite(user)
        await self._audit_log(
            AuditAction.ADMIN_INVITE_RESENT,
            user_id=user.id,
            extra={"email": user.email},
        )
        return user

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

    async def assign_role(self, user_id: UUID, role_name: str) -> User:
        """Kullanıcıya rol atar.

        Verilen isimde rol veritabanında aranır, bulunursa kullanıcıya
        atanır. Rol değişikliğinde permission cache invalidate edilir.

        Args:
            user_id: Rolü değiştirilecek kullanıcının UUID'si.
            role_name: Atanacak rolün adı (ör: "admin", "accountant").

        Returns:
            Güncellenmiş kullanıcı nesnesi.

        Raises:
            UserNotFoundError: Kullanıcı bulunamadığında.
            NotFoundError: Belirtilen isimde rol bulunamadığında.
        """
        current = await self._repo.get_by_id_or_raise(user_id)

        new_role = await self._role_repo.get_by_name(role_name)
        if not new_role:
            raise NotFoundError(f"'{role_name}' adında bir rol bulunamadı.")

        old_role_name = current.role.name if current.role else None
        await self._invalidate_user_cache(user_id, current.email, invalidate_permissions=True)
        updated = await self._repo.update(user_id, role_id=new_role.id)
        await self._audit_log(
            AuditAction.ROLE_CHANGED,
            user_id=user_id,
            extra={"old_role": old_role_name, "new_role": role_name},
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
