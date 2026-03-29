"""
SQLAdmin kimlik doğrulama backend'i.
Mevcut JWT sistemi ve UserRole.ADMIN kontrolü kullanılır.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqladmin.authentication import AuthenticationBackend

from app.core.exceptions import AppError
from app.core.security import TokenType, decode_token
from app.db.models.user import UserRole
from app.db.repositories.user import UserRepository
from app.db.session import AsyncSessionFactory

if TYPE_CHECKING:
    from starlette.requests import Request


class AdminAuthBackend(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        """
        Admin login formu — email/password ile giriş.
        Başarılıysa JWT token'ı session'a kaydeder.
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
            return False

    async def logout(self, request: Request) -> bool:
        """Session'dan token'ı temizle."""
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        """
        Her admin isteğinde token doğrula ve ADMIN rolü kontrol et.
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
            return False
