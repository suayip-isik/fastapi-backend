"""
AccountService — hesap yönetimi işlemleri.

Sorumluluklar:
    - verify_email · resend_verification — Email doğrulama
    - forgot_password · reset_password — Şifre sıfırlama
    - update_profile · change_password · delete_account — Profil yönetimi
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.adapters.infrastructure import ARQTaskQueueAdapter, RedisAdapter
from app.core.config import settings
from app.core.exceptions import AuthenticationError, InvalidTokenError, NotFoundError
from app.core.i18n import language_var, t
from app.core.security import hash_password, verify_password
from app.db.models.audit_log import AuditAction
from app.db.models.user import SurfaceType
from app.db.repositories.user import UserRepository
from app.services._keys import (
    EMAIL_VERIFY_KEY,
    PASSWORD_RESET_KEY,
    decode_email_verify_value,
    encode_email_verify_value,
)
from app.services.api_key import APIKeyService
from app.services.base import AuditableMixin
from app.tasks.worker import (
    send_admin_password_reset_email,
    send_password_reset_email,
    send_verification_email,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.ports.infrastructure import RedisPort, TaskQueuePort
    from app.services.audit import AuditService


class AccountService(AuditableMixin):
    """Hesap yonetimi (email verify, sifre reset, profil islemleri) servisidir."""

    def __init__(
        self,
        session: AsyncSession,
        audit: AuditService | None = None,
        *,
        redis: RedisPort | None = None,
        task_queue: TaskQueuePort | None = None,
    ) -> None:
        """AccountService nesnesini gerekli bagimliliklarla olusturur."""
        self._session = session
        self._repo = UserRepository(session)
        self._audit = audit
        self._redis = redis or RedisAdapter()
        self._task_queue = task_queue or ARQTaskQueueAdapter()

    # ── Email Verification ────────────────────────────────────────────────────

    async def verify_email(self, token: str) -> None:
        """Token geçerliyse kullanıcıyı doğrulanmış olarak işaretle."""
        raw_value = await self._redis.get(EMAIL_VERIFY_KEY.format(token))
        if not raw_value:
            raise InvalidTokenError(t("error.auth.invalid_verify_token"))

        await self._redis.delete(EMAIL_VERIFY_KEY.format(token))
        user_id, target_email = decode_email_verify_value(raw_value)

        user = await self._repo.get_by_id(UUID(user_id))
        if not user:
            raise InvalidTokenError(t("error.auth.user_not_found"))

        if target_email and user.pending_email == target_email:
            previous_email = user.email
            await self._repo.update(
                user.id,
                email=target_email,
                pending_email=None,
                is_verified=True,
            )
            await self._audit_log(
                AuditAction.EMAIL_CHANGED,
                user_id=user.id,
                extra={
                    "target_user_id": str(user.id),
                    "old_email": previous_email,
                    "new_email": target_email,
                },
            )
            return

        if target_email and user.email != target_email:
            raise InvalidTokenError(t("error.auth.invalid_verify_token"))

        if not user.is_verified:
            await self._repo.update(user.id, is_verified=True)

        await self._audit_log(
            AuditAction.EMAIL_VERIFIED,
            user_id=user.id,
            extra={"target_user_id": str(user.id)},
        )

    async def resend_verification(self, email: str) -> None:
        """Doğrulama e-postasını yeniden gönder. Kullanıcı yoksa sessizce döner."""
        user = await self._repo.get_active_by_email(email)
        target_email = email.lower()
        if user and not user.is_verified:
            target_email = user.email
        else:
            user = await self._repo.get_active_by_pending_email(email)
            if not user or not user.pending_email:
                return
            target_email = user.pending_email

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
        await self._audit_log(
            AuditAction.VERIFICATION_RESENT,
            user_id=user.id,
            extra={"target_user_id": str(user.id), "verification_email": target_email},
        )

    # ── Password Reset ────────────────────────────────────────────────────────

    async def forgot_password(
        self,
        email: str,
    ) -> None:
        """Şifre sıfırlama e-postası gönder. Kullanıcı yoksa sessizce döner."""
        user = await self._repo.get_active_by_email(email)
        if not user or not user.hashed_password:
            return  # Şifresi olmayan ya da var olmayan e-posta — user enumeration yok

        surface = SurfaceType(user.surface)
        token = secrets.token_urlsafe(32)
        await self._redis.setex(
            PASSWORD_RESET_KEY.format(token), settings.PASSWORD_RESET_TTL, str(user.id)
        )
        await self._task_queue.enqueue(
            self._get_password_reset_task(surface),
            user.email,
            token,
            language_var.get(),
        )

        await self._audit_log(
            self._get_password_reset_requested_action(surface),
            user_id=user.id,
        )

    async def reset_password(
        self,
        token: str,
        new_password: str,
    ) -> None:
        """Token geçerliyse şifreyi güncelle."""
        user_id = await self._redis.get(PASSWORD_RESET_KEY.format(token))
        if not user_id:
            raise InvalidTokenError(t("error.auth.invalid_reset_token"))

        user = await self._repo.get_by_id(UUID(user_id))
        if not user or not user.is_active:
            raise InvalidTokenError(t("error.auth.user_not_found"))

        await self._redis.delete(PASSWORD_RESET_KEY.format(token))

        surface = SurfaceType(user.surface)
        revoked_after = datetime.now(UTC)
        update_data: dict[str, object] = {
            "hashed_password": hash_password(new_password),
            "session_revoked_after": revoked_after,
        }
        if user.surface == SurfaceType.ADMIN.value and not user.is_verified:
            update_data["is_verified"] = True

        await self._repo.update(user.id, **update_data)
        await APIKeyService(self._session, audit=self._audit).revoke_all_for_user(
            user.id,
            reason="password_reset",
        )
        await self._audit_log(self._get_password_reset_action(surface), user_id=user.id)

    def _get_password_reset_task(
        self, surface: SurfaceType
    ) -> Callable[..., Awaitable[dict[str, Any]]]:
        if surface is SurfaceType.ADMIN:
            return send_admin_password_reset_email
        return send_password_reset_email

    def _get_password_reset_requested_action(self, surface: SurfaceType) -> AuditAction:
        if surface is SurfaceType.ADMIN:
            return AuditAction.ADMIN_PASSWORD_RESET_REQUESTED
        return AuditAction.PASSWORD_RESET_REQUESTED

    def _get_password_reset_action(self, surface: SurfaceType) -> AuditAction:
        if surface is SurfaceType.ADMIN:
            return AuditAction.ADMIN_PASSWORD_RESET
        return AuditAction.PASSWORD_RESET

    # ── Profile Management ─────────────────────────────────────────────────────

    async def update_profile(
        self,
        user_id: UUID,
        *,
        username: str | None = None,
        full_name: str | None = None,
        avatar_url: str | None = None,
    ) -> None:
        """Kullanıcı profil bilgilerini günceller.

        Sadece sağlanan alanlar güncellenir, None değerler göz ardı edilir.

        Args:
            user_id: Güncellenecek kullanıcının benzersiz kimliği.
            username: Yeni kullanıcı adı. Benzersiz olmalıdır.
            full_name: Kullanıcının tam adı.
            avatar_url: Profil fotoğrafı URL'i.

        Raises:
            NotFoundError: Kullanıcı bulunamazsa.

        Example:
            >>> await account_service.update_profile(
            ...     user_id=uuid,
            ...     username="yeni_kullanici",
            ...     full_name="Ahmet Yılmaz"
            ... )
        """
        user = await self._repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(t("error.auth.user_not_found"))

        update_data: dict[str, str] = {}
        if username is not None:
            update_data["username"] = username
        if full_name is not None:
            update_data["full_name"] = full_name
        if avatar_url is not None:
            update_data["avatar_url"] = avatar_url

        if update_data:
            await self._repo.update(user_id, **update_data)
            await self._audit_log(AuditAction.PROFILE_UPDATED, user_id=user_id)

    async def change_password(
        self,
        user_id: UUID,
        current_password: str,
        new_password: str,
    ) -> None:
        """Kullanıcının mevcut şifresini doğrulayarak yeni şifre belirler.

        Şifre değişikliği için mevcut şifrenin doğru girilmesi zorunludur.

        Args:
            user_id: Şifresi değiştirilecek kullanıcının benzersiz kimliği.
            current_password: Kullanıcının mevcut şifresi (doğrulama için).
            new_password: Belirlenmek istenen yeni şifre.

        Raises:
            NotFoundError: Kullanıcı bulunamazsa.
            AuthenticationError: Mevcut şifre yanlışsa veya şifre belirlenmemişse.

        Example:
            >>> await account_service.change_password(
            ...     user_id=uuid,
            ...     current_password="eski_sifre123",
            ...     new_password="yeni_sifre456"
            ... )
        """
        user = await self._repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(t("error.auth.user_not_found"))

        if not user.hashed_password:
            raise AuthenticationError(t("error.auth.no_password"))

        if not verify_password(current_password, user.hashed_password):
            raise AuthenticationError(t("error.auth.wrong_password"))

        await self._repo.update(user_id, hashed_password=hash_password(new_password))
        await self._audit_log(AuditAction.PASSWORD_CHANGED, user_id=user_id)

    async def delete_account(self, user_id: UUID, password: str | None = None) -> None:
        """Kullanıcı hesabını kalıcı olarak siler.

        Şifre doğrulaması yapıldıktan sonra hesap ve ilişkili tüm veriler
        veritabanından kaldırılır. Bu işlem geri alınamaz.

        Args:
            user_id: Silinecek kullanıcının benzersiz kimliği.
            password: Kullanıcının şifresi (doğrulama için).

        Raises:
            NotFoundError: Kullanıcı bulunamazsa.
            AuthenticationError: Şifre yanlışsa.

        Warning:
            Bu işlem geri alınamaz. Tüm kullanıcı verileri kalıcı olarak silinir.

        Example:
            >>> await account_service.delete_account(
            ...     user_id=uuid,
            ...     password="mevcut_sifre123"
            ... )
        """
        user = await self._repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(t("error.auth.user_not_found"))

        if (
            user.hashed_password
            and password
            and not verify_password(password, user.hashed_password)
        ):
            raise AuthenticationError(t("error.auth.password_wrong"))

        await self._audit_log(AuditAction.ACCOUNT_DELETED, user_id=user_id)
        await self._repo.delete(user_id)
