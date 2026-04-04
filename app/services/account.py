"""
AccountService — hesap yönetimi işlemleri.

Sorumluluklar:
    - verify_email · resend_verification — Email doğrulama
    - forgot_password · reset_password — Şifre sıfırlama
    - update_profile · change_password · delete_account — Profil yönetimi
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING
from uuid import UUID

from app.core.config import settings
from app.core.exceptions import AuthenticationError, InvalidTokenError, NotFoundError
from app.core.redis import get_redis_client
from app.core.security import hash_password, verify_password
from app.db.models.audit_log import AuditAction
from app.db.repositories.user import UserRepository
from app.services._keys import EMAIL_VERIFY_KEY, PASSWORD_RESET_KEY
from app.services.base import AuditableMixin
from app.tasks.worker import enqueue, send_password_reset_email, send_verification_email

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.audit import AuditService


class AccountService(AuditableMixin):
    """Hesap yonetimi (email verify, sifre reset, profil islemleri) servisidir."""

    def __init__(self, session: AsyncSession, audit: AuditService | None = None) -> None:
        """AccountService nesnesini gerekli bagimliliklarla olusturur."""
        self._repo = UserRepository(session)
        self._audit = audit

    # ── Email Verification ────────────────────────────────────────────────────

    async def verify_email(self, token: str) -> None:
        """Token geçerliyse kullanıcıyı doğrulanmış olarak işaretle."""
        redis = await get_redis_client()
        user_id = await redis.get(EMAIL_VERIFY_KEY.format(token))
        if not user_id:
            raise InvalidTokenError("Geçersiz veya süresi dolmuş doğrulama token'ı.")

        await redis.delete(EMAIL_VERIFY_KEY.format(token))

        user = await self._repo.get_by_id(UUID(user_id))
        if not user:
            raise InvalidTokenError("Kullanıcı bulunamadı.")

        if not user.is_verified:
            await self._repo.update(user.id, is_verified=True)

        await self._audit_log(AuditAction.EMAIL_VERIFIED, user_id=user.id)

    async def resend_verification(self, email: str) -> None:
        """Doğrulama e-postasını yeniden gönder. Kullanıcı yoksa sessizce döner."""
        user = await self._repo.get_active_by_email(email)
        if not user or user.is_verified:
            return

        token = secrets.token_urlsafe(32)
        redis = await get_redis_client()
        await redis.setex(EMAIL_VERIFY_KEY.format(token), settings.EMAIL_VERIFY_TTL, str(user.id))
        await enqueue(send_verification_email, user.email, token)

    # ── Password Reset ────────────────────────────────────────────────────────

    async def forgot_password(self, email: str) -> None:
        """Şifre sıfırlama e-postası gönder. Kullanıcı yoksa sessizce döner."""
        user = await self._repo.get_active_by_email(email)
        if not user or not user.hashed_password:
            return  # Şifresi olmayan ya da var olmayan e-posta — user enumeration yok

        token = secrets.token_urlsafe(32)
        redis = await get_redis_client()
        await redis.setex(
            PASSWORD_RESET_KEY.format(token), settings.PASSWORD_RESET_TTL, str(user.id)
        )
        await enqueue(send_password_reset_email, user.email, token)

        await self._audit_log(AuditAction.PASSWORD_RESET_REQUESTED, user_id=user.id)

    async def reset_password(self, token: str, new_password: str) -> None:
        """Token geçerliyse şifreyi güncelle."""
        redis = await get_redis_client()
        user_id = await redis.get(PASSWORD_RESET_KEY.format(token))
        if not user_id:
            raise InvalidTokenError("Geçersiz veya süresi dolmuş şifre sıfırlama token'ı.")

        await redis.delete(PASSWORD_RESET_KEY.format(token))

        user = await self._repo.get_by_id(UUID(user_id))
        if not user or not user.is_active:
            raise InvalidTokenError("Kullanıcı bulunamadı.")

        await self._repo.update(user.id, hashed_password=hash_password(new_password))
        await self._audit_log(AuditAction.PASSWORD_RESET, user_id=user.id)

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
            raise NotFoundError("Kullanıcı bulunamadı.")

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
            raise NotFoundError("Kullanıcı bulunamadı.")

        if not user.hashed_password:
            raise AuthenticationError("Bu hesap için şifre değiştirilemez.")

        if not verify_password(current_password, user.hashed_password):
            raise AuthenticationError("Mevcut şifre hatalı.")

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
            raise NotFoundError("Kullanıcı bulunamadı.")

        if (
            user.hashed_password
            and password
            and not verify_password(password, user.hashed_password)
        ):
            raise AuthenticationError("Şifre hatalı.")

        await self._audit_log(AuditAction.ACCOUNT_DELETED, user_id=user_id)
        await self._repo.delete(user_id)
