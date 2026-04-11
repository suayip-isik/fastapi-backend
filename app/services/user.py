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
    AuthenticationError,
    BusinessRuleError,
    InsufficientPermissionsError,
    NotFoundError,
    UserNotFoundError,
)
from app.core.i18n import language_var, t
from app.core.permissions import Permission
from app.core.security import hash_password, verify_password
from app.db.models.audit_log import AuditAction
from app.db.models.user import SurfaceType
from app.db.repositories.role import RoleRepository
from app.db.repositories.user import UserRepository
from app.services._keys import (
    EMAIL_VERIFY_KEY,
    PASSWORD_RESET_KEY,
    USER_CACHE_KEY,
    USER_CACHE_TTL,
    USER_EMAIL_CACHE_KEY,
    USER_PERMISSIONS_KEY,
    encode_email_verify_value,
)
from app.services.base import AuditableMixin
from app.services.cache import CacheService
from app.tasks.worker import send_admin_invite_email, send_verification_email

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.role import Role
    from app.db.models.user import User
    from app.ports.infrastructure import RedisPort, TaskQueuePort
    from app.schemas.user import (
        AdminChangeUserEmailRequest,
        AdminUpdateUserRequest,
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

    async def _get_admin_role_or_raise(self, role_name: str) -> Role:
        role = await self._role_repo.get_by_name(role_name)
        if not role:
            raise NotFoundError(f"'{role_name}' adında bir rol bulunamadı.")
        if Permission.ADMIN_PANEL_ACCESS.value not in role.permission_set:
            raise BusinessRuleError("Admin kullanıcıya yalnızca panel erişimi olan rol atanabilir.")
        return role

    def _mask_email(self, email: str | None) -> str | None:
        if not email or "@" not in email:
            return email
        local, domain = email.split("@", 1)
        if len(local) <= 2:
            masked_local = local[0] + "*"
        else:
            masked_local = local[0] + ("*" * (len(local) - 2)) + local[-1]
        return f"{masked_local}@{domain}"

    async def _issue_verification_email(self, user: User, target_email: str) -> str:
        token = secrets.token_urlsafe(32)
        await self._redis.setex(
            EMAIL_VERIFY_KEY.format(token),
            settings.EMAIL_VERIFY_TTL,
            encode_email_verify_value(str(user.id), target_email),
        )
        await self._task_queue.enqueue(
            send_verification_email,
            target_email,
            token,
            language_var.get(),
        )
        return token

    async def _audit_user_management_blocked(
        self,
        *,
        actor_user_id: UUID,
        target_user: User,
        operation: str,
        reason: str,
    ) -> None:
        await self._audit_log(
            AuditAction.USER_MANAGEMENT_BLOCKED,
            user_id=actor_user_id,
            extra={
                "actor_user_id": str(actor_user_id),
                "target_user_id": str(target_user.id),
                "target_role": target_user.role.name if target_user.role else None,
                "operation": operation,
                "reason": reason,
            },
        )

    async def _get_manageable_target_or_raise(
        self,
        *,
        actor_user_id: UUID,
        target_user_id: UUID,
        operation: str,
        include_deleted: bool = False,
    ) -> User:
        if include_deleted:
            target_user = await self._repo.get_by_id(target_user_id, include_deleted=True)
            if not target_user:
                raise UserNotFoundError()
        else:
            target_user = await self._repo.get_by_id_or_raise(target_user_id)

        if target_user.id == actor_user_id:
            await self._audit_user_management_blocked(
                actor_user_id=actor_user_id,
                target_user=target_user,
                operation=operation,
                reason="self_action",
            )
            raise InsufficientPermissionsError(t("error.user.self_action"))

        if target_user.role and target_user.role.name == "admin":
            await self._audit_user_management_blocked(
                actor_user_id=actor_user_id,
                target_user=target_user,
                operation=operation,
                reason="protected_admin_role",
            )
            raise InsufficientPermissionsError(t("error.user.protected_admin"))

        return target_user

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

    async def update_self(self, user_id: UUID, data: UpdateUserRequest) -> User:
        """Kullanıcının kendi profilini günceller."""
        user = await self._repo.get_by_id_or_raise(user_id)
        update_data = data.model_dump(exclude_unset=True)
        new_email = update_data.pop("email", None)
        current_password = update_data.pop("current_password", None)

        if new_email is not None and new_email.lower() != user.email:
            if not user.hashed_password:
                raise BusinessRuleError(t("error.auth.no_password"))
            if not current_password or not verify_password(current_password, user.hashed_password):
                raise AuthenticationError(t("error.auth.wrong_password"))
            if await self._repo.email_exists(new_email, exclude_user_id=user.id):
                raise AlreadyExistsError("Bu e-posta adresi zaten kullanılıyor.")

            normalized_email = new_email.lower()
            await self._invalidate_user_cache(user_id, user.email)
            updated = await self._repo.update(
                user_id,
                pending_email=normalized_email,
                is_verified=False,
            )
            await self._issue_verification_email(updated, normalized_email)
            await self._audit_log(
                AuditAction.EMAIL_CHANGE_REQUESTED,
                user_id=user_id,
                extra={
                    "actor_user_id": str(user_id),
                    "target_user_id": str(user_id),
                    "old_email": self._mask_email(user.email),
                    "new_email": self._mask_email(normalized_email),
                },
            )
            user = updated

        if "password" in update_data:
            update_data["hashed_password"] = hash_password(update_data.pop("password"))

        if update_data:
            await self._invalidate_user_cache(user_id, user.email)
            user = await self._repo.update(user_id, **update_data)
            await self._audit_log(
                AuditAction.PROFILE_UPDATED,
                user_id=user_id,
                extra={"actor_user_id": str(user_id), "target_user_id": str(user_id)},
            )

        return user

    async def admin_update(
        self,
        *,
        actor_user_id: UUID,
        user_id: UUID,
        data: AdminUpdateUserRequest,
    ) -> User:
        """Admin user-management ile kullanıcı profil alanlarını günceller."""
        target_user = await self._get_manageable_target_or_raise(
            actor_user_id=actor_user_id,
            target_user_id=user_id,
            operation="update_user",
        )
        update_data = data.model_dump(exclude_unset=True)
        if update_data.get("username"):
            existing = await self._repo.get_by_username(update_data["username"])
            if existing and existing.id != target_user.id:
                raise AlreadyExistsError("Bu kullanıcı adı zaten kullanılıyor.")

        await self._invalidate_user_cache(target_user.id, target_user.email)
        updated = await self._repo.update(target_user.id, **update_data)
        await self._audit_log(
            AuditAction.PROFILE_UPDATED,
            user_id=actor_user_id,
            extra={
                "actor_user_id": str(actor_user_id),
                "target_user_id": str(target_user.id),
                "operation": "admin_update_user",
            },
        )
        return updated

    async def admin_change_email(
        self,
        *,
        actor_user_id: UUID,
        user_id: UUID,
        data: AdminChangeUserEmailRequest,
    ) -> User:
        """Admin user-management ile hedef kullanıcının e-posta değişikliğini başlatır."""
        target_user = await self._get_manageable_target_or_raise(
            actor_user_id=actor_user_id,
            target_user_id=user_id,
            operation="change_email",
        )
        normalized_email = data.email.lower()
        if normalized_email == target_user.email:
            raise BusinessRuleError("Yeni e-posta adresi mevcut adresle aynı olamaz.")
        if await self._repo.email_exists(normalized_email, exclude_user_id=target_user.id):
            raise AlreadyExistsError("Bu e-posta adresi zaten kullanılıyor.")

        await self._invalidate_user_cache(target_user.id, target_user.email)
        updated = await self._repo.update(
            target_user.id,
            pending_email=normalized_email,
            is_verified=False,
        )
        await self._issue_verification_email(updated, normalized_email)
        await self._audit_log(
            AuditAction.EMAIL_CHANGE_REQUESTED,
            user_id=actor_user_id,
            extra={
                "actor_user_id": str(actor_user_id),
                "target_user_id": str(target_user.id),
                "old_email": self._mask_email(target_user.email),
                "new_email": self._mask_email(normalized_email),
            },
        )
        return updated

    async def resend_user_verification(
        self,
        *,
        actor_user_id: UUID,
        user_id: UUID,
    ) -> None:
        """Admin user-management ile hedef kullanıcıya doğrulama maili gönderir."""
        target_user = await self._get_manageable_target_or_raise(
            actor_user_id=actor_user_id,
            target_user_id=user_id,
            operation="resend_verification",
        )
        verification_email = target_user.pending_email
        if verification_email is None and not target_user.is_verified:
            verification_email = target_user.email
        if verification_email is None:
            raise BusinessRuleError("Kullanıcının bekleyen bir e-posta doğrulaması yok.")

        await self._issue_verification_email(target_user, verification_email)
        await self._audit_log(
            AuditAction.VERIFICATION_RESENT,
            user_id=actor_user_id,
            extra={
                "actor_user_id": str(actor_user_id),
                "target_user_id": str(target_user.id),
                "verification_email": self._mask_email(verification_email),
            },
        )

    async def create_admin_user(self, data: CreateAdminUserRequest, *, actor_user_id: UUID) -> User:
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
            surface=SurfaceType.ADMIN.value,
            is_active=True,
            is_verified=False,
            hashed_password=None,
        )
        await self._issue_admin_invite(user)
        await self._audit_log(
            AuditAction.ADMIN_USER_CREATED,
            user_id=actor_user_id,
            extra={
                "actor_user_id": str(actor_user_id),
                "target_user_id": str(user.id),
                "email": self._mask_email(user.email),
                "role_name": role.name,
            },
        )
        return user

    async def resend_admin_invite(self, user_id: UUID, *, actor_user_id: UUID) -> User:
        """Şifresi henüz belirlenmemiş admin kullanıcıya daveti yeniden gönderir."""
        user = await self._repo.get_by_id_or_raise(user_id)
        if user.id == actor_user_id:
            await self._audit_user_management_blocked(
                actor_user_id=actor_user_id,
                target_user=user,
                operation="resend_admin_invite",
                reason="self_action",
            )
            raise InsufficientPermissionsError(t("error.user.self_action"))
        if user.role and user.role.name == "admin":
            await self._audit_user_management_blocked(
                actor_user_id=actor_user_id,
                target_user=user,
                operation="resend_admin_invite",
                reason="protected_admin_role",
            )
            raise InsufficientPermissionsError(t("error.user.protected_admin"))
        if user.surface != SurfaceType.ADMIN.value:
            raise BusinessRuleError(
                "Yalnızca admin tipindeki kullanıcılar için davet gönderilebilir."
            )
        if user.hashed_password:
            raise BusinessRuleError(
                "Şifresi belirlenmiş admin kullanıcıya davet yeniden gönderilemez."
            )

        await self._issue_admin_invite(user)
        await self._audit_log(
            AuditAction.ADMIN_INVITE_RESENT,
            user_id=actor_user_id,
            extra={
                "actor_user_id": str(actor_user_id),
                "target_user_id": str(user.id),
                "email": self._mask_email(user.email),
            },
        )
        return user

    async def deactivate(self, user_id: UUID, *, actor_user_id: UUID) -> User:
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
        user = await self._get_manageable_target_or_raise(
            actor_user_id=actor_user_id,
            target_user_id=user_id,
            operation="deactivate_user",
        )
        await self._invalidate_user_cache(user_id, user.email)
        updated = await self._repo.update(user_id, is_active=False)
        await self._audit_log(
            AuditAction.USER_DEACTIVATED,
            user_id=actor_user_id,
            extra={"actor_user_id": str(actor_user_id), "target_user_id": str(user_id)},
        )
        return updated

    async def activate(self, user_id: UUID, *, actor_user_id: UUID) -> User:
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
        user = await self._get_manageable_target_or_raise(
            actor_user_id=actor_user_id,
            target_user_id=user_id,
            operation="activate_user",
        )
        await self._invalidate_user_cache(user_id, user.email)
        updated = await self._repo.update(user_id, is_active=True)
        await self._audit_log(
            AuditAction.USER_ACTIVATED,
            user_id=actor_user_id,
            extra={"actor_user_id": str(actor_user_id), "target_user_id": str(user_id)},
        )
        return updated

    async def assign_role(self, user_id: UUID, role_name: str, *, actor_user_id: UUID) -> User:
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
        current = await self._get_manageable_target_or_raise(
            actor_user_id=actor_user_id,
            target_user_id=user_id,
            operation="assign_role",
        )

        new_role = await self._role_repo.get_by_name(role_name)
        if not new_role:
            raise NotFoundError(f"'{role_name}' adında bir rol bulunamadı.")

        old_role_name = current.role.name if current.role else None
        await self._invalidate_user_cache(user_id, current.email, invalidate_permissions=True)
        updated = await self._repo.update(user_id, role_id=new_role.id)
        await self._audit_log(
            AuditAction.ROLE_CHANGED,
            user_id=actor_user_id,
            extra={
                "actor_user_id": str(actor_user_id),
                "target_user_id": str(user_id),
                "old_role": old_role_name,
                "new_role": role_name,
            },
        )
        return updated

    async def soft_delete(self, user_id: UUID, *, actor_user_id: UUID) -> None:
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
        user = await self._get_manageable_target_or_raise(
            actor_user_id=actor_user_id,
            target_user_id=user_id,
            operation="delete_user",
        )
        if user.is_deleted:
            raise BusinessRuleError("Kullanıcı zaten silinmiş.")
        await self._invalidate_user_cache(user_id, user.email)
        await self._repo.soft_delete(user_id)
        await self._audit_log(
            AuditAction.USER_DELETED,
            user_id=actor_user_id,
            extra={"actor_user_id": str(actor_user_id), "target_user_id": str(user_id)},
        )

    async def restore(self, user_id: UUID, *, actor_user_id: UUID) -> User:
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
        user = await self._get_manageable_target_or_raise(
            actor_user_id=actor_user_id,
            target_user_id=user_id,
            operation="restore_user",
            include_deleted=True,
        )
        if not user.is_deleted:
            raise BusinessRuleError("Kullanıcı silinmemiş.")
        await self._invalidate_user_cache(user_id, user.email)
        restored = await self._repo.restore(user_id)
        await self._audit_log(
            AuditAction.USER_RESTORED,
            user_id=actor_user_id,
            extra={"actor_user_id": str(actor_user_id), "target_user_id": str(user_id)},
        )
        return restored
