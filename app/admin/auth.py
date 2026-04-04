"""
SQLAdmin kimlik doğrulama backend'i.
Mevcut JWT sistemi ve UserRole.ADMIN kontrolü kullanılır.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqladmin.authentication import AuthenticationBackend

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.core.security import TokenType, decode_token
from app.db.models.user import UserRole
from app.db.repositories.user import UserRepository
from app.db.session import AsyncSessionFactory

if TYPE_CHECKING:
    from starlette.requests import Request

logger = get_logger(__name__)


class AdminAuthBackend(AuthenticationBackend):
    """SQLAdmin panel için JWT tabanlı authentication backend.

    Admin paneline erişimi JWT token ile kontrol eder. Sadece ADMIN
    rolüne sahip kullanıcılar panele girebilir. Token session'dan
    okunur ve her istekte validate edilir.

    Note:
        - Sadece UserRole.ADMIN yetkisi yeterli
        - Token validation core.security modülünü kullanır
        - Login başarısız ise /admin/login'e redirect
        - Token session cookie'de saklanır

    Example:
        >>> # Browser: Session cookie ile otomatik auth
        >>> # GET /admin -> Admin panel (ADMIN rolü gerekli)
    """

    async def login(self, request: Request) -> bool:
        """Admin login formu ile email/password doğrulama.

        Kullanıcı email ve password ile giriş yapar. Başarılı
        doğrulamadan sonra JWT access token üretilir ve session'a
        kaydedilir. Sadece aktif ve ADMIN rolüne sahip kullanıcılar
        giriş yapabilir.

        Args:
            request: Starlette Request objesi. Form data'dan username
                (email) ve password alanlarını okur.

        Returns:
            True: Login başarılı, token session'a kaydedildi
            False: Login başarısız (geçersiz credentials, yetkisiz vb.)

        Note:
            - Form field'ları: username (email), password
            - Şifresi olmayan kullanıcılar (hashed_password=None) giriş yapamaz
            - Exception durumunda False döner (güvenlik)

        Example:
            >>> # POST /admin/login ile form gönderilir
            >>> # username: admin@example.com
            >>> # password: securepass
            >>> # -> Success: Session'a token yazılır
        """
        form = await request.form()
        email = str(form.get("username", ""))
        password = str(form.get("password", ""))

        if not email or not password:
            return False

        try:
            from app.core.security import create_access_token, verify_password

            async with AsyncSessionFactory() as session:
                repo = UserRepository(session)
                user = await repo.get_active_by_email(email)

                if not user:
                    return False

                if not user.hashed_password:
                    return False

                if not verify_password(password, user.hashed_password):
                    return False

                if user.role != UserRole.ADMIN:
                    return False

                token = create_access_token(str(user.id))
                request.session["admin_token"] = token
                return True

        except Exception:
            logger.warning("admin_login_unexpected_error", exc_info=True)
            return False

    async def logout(self, request: Request) -> bool:
        """Admin kullanıcı çıkışı - session temizleme.

        Kullanıcı oturumunu sonlandırır. Session içindeki tüm
        veriler (token dahil) temizlenir. Logout sonrası kullanıcı
        admin paneline erişemez.

        Args:
            request: Starlette Request objesi. Session verileri
                bu objeden temizlenir.

        Returns:
            Her zaman True döner (logout daima başarılıdır).

        Example:
            >>> # GET /admin/logout
            >>> # -> Session temizlenir, login sayfasına redirect
        """
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        """Her admin isteğinde token doğrulama ve yetki kontrolü.

        Admin paneline gelen her istekte çağrılır. Session'daki
        JWT token'ı decode eder, geçerliliğini ve kullanıcının
        ADMIN rolüne sahip olduğunu kontrol eder. Başarısız
        durumda erişim reddedilir.

        Args:
            request: Starlette Request objesi. Session'dan token
                okunur.

        Returns:
            True: Token geçerli ve kullanıcı ADMIN rolünde
            False: Token geçersiz, kullanıcı yetkisiz veya hata

        Note:
            - Token TokenType.ACCESS olmalı
            - Kullanıcı aktif (is_active=True) olmalı
            - Kullanıcı UserRole.ADMIN olmalı
            - Herhangi bir hata durumunda False döner

        Example:
            >>> # Her admin panel isteğinde otomatik çalışır
            >>> # GET /admin/user -> authenticate() check
            >>> # -> True ise panel gösterilir
            >>> # -> False ise login'e redirect
        """
        token = request.session.get("admin_token")
        if not token:
            return False

        try:
            payload = decode_token(token)

            if payload.type != TokenType.ACCESS:
                return False

            async with AsyncSessionFactory() as session:
                repo = UserRepository(session)
                user = await repo.get_by_id(UUID(payload.sub))

                if not user or not user.is_active:
                    return False

                if user.role != UserRole.ADMIN:
                    return False

            return True

        except AppError:
            return False
        except Exception:
            logger.warning("admin_authenticate_unexpected_error", exc_info=True)
            return False
