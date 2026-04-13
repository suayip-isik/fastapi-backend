"""SQLAdmin authentication adapter ve use-case'leri."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from redis.exceptions import RedisError
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy.exc import SQLAlchemyError

from app.adapters.infrastructure import RedisAdapter
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.core.permissions import has_admin_surface_access
from app.core.security import (
    TokenType,
    create_access_token,
    decode_token,
    is_token_revoked_after,
    verify_password,
)
from app.db.models.user import SurfaceType, User
from app.db.repositories.user import UserRepository
from app.db.session_provider import AsyncSessionFactoryProtocol, get_default_session_factory
from app.services._keys import BLACKLIST_KEY
from app.services.permissions import PermissionCache, PermissionProvider, PermissionQueryService

if TYPE_CHECKING:
    from starlette.requests import Request

    from app.ports.infrastructure import RedisPort

logger = get_logger(__name__)


@dataclass(slots=True)
class AdminLoginResult:
    token: str
    permissions: set[str]


class AdminUserReaderProtocol(Protocol):
    """Admin auth için gerekli user lookup davranışı."""

    async def get_active_by_email(self, email: str) -> User | None:
        """Aktif kullanıcıyı email ile getir."""

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Kullanıcıyı id ile getir."""


class AdminUserReader:
    """Admin auth için salt-okunur user gateway."""

    def __init__(self, session_factory: AsyncSessionFactoryProtocol) -> None:
        self._session_factory = session_factory

    async def get_active_by_email(self, email: str) -> User | None:
        async with self._session_factory() as session, session.begin():
            return await UserRepository(session).get_active_by_email(email)

    async def get_by_id(self, user_id: UUID) -> User | None:
        async with self._session_factory() as session, session.begin():
            return await UserRepository(session).get_by_id(user_id)


class AdminAuthUseCase:
    """Admin panel login ve session doğrulama akışını yönetir."""

    def __init__(
        self,
        *,
        user_reader: AdminUserReaderProtocol,
        permission_provider: PermissionProvider | None = None,
        redis: RedisPort | None = None,
    ) -> None:
        self._user_reader = user_reader
        self._redis = redis or RedisAdapter()
        self._permission_provider = permission_provider or PermissionProvider(
            query_service=PermissionQueryService(get_default_session_factory()),
            cache=PermissionCache(RedisAdapter()),
        )

    async def login_with_password(self, email: str, password: str) -> AdminLoginResult | None:
        if not email or not password:
            return None

        try:
            user = await self._user_reader.get_active_by_email(email)
        except SQLAlchemyError:
            logger.warning("admin_login_user_lookup_failed", exc_info=True)
            return None

        try:
            if not user or not user.hashed_password:
                return None

            if not verify_password(password, user.hashed_password):
                return None

            if user.surface != SurfaceType.ADMIN.value:
                return None

            user_perms = await self._permission_provider.get_permissions(user.id)
            if not has_admin_surface_access(user_perms):
                return None

            return AdminLoginResult(
                token=create_access_token(str(user.id)),
                permissions=user_perms,
            )
        except (RedisError, SQLAlchemyError, OSError, ValueError, TypeError, AppError):
            logger.warning("admin_login_authorization_failed", exc_info=True)
            return None

    async def authenticate_session_token(self, token: str | None) -> bool:
        if not token:
            return False

        try:
            payload = decode_token(token)
            if payload.type != TokenType.ACCESS:
                return False
            if await self._redis.exists(BLACKLIST_KEY.format(payload.jti)):
                return False

            user = await self._user_reader.get_by_id(UUID(payload.sub))
            if not user or not user.is_active:
                return False
            if is_token_revoked_after(payload.iat, user.session_revoked_after):
                return False

            if user.surface != SurfaceType.ADMIN.value:
                return False

            user_perms = await self._permission_provider.get_permissions(user.id)
            return has_admin_surface_access(user_perms)
        except (AppError, RedisError, SQLAlchemyError, OSError, ValueError, TypeError):
            return False


class AdminAuthBackend(AuthenticationBackend):
    """SQLAdmin için request/session adapter'ı."""

    def __init__(
        self,
        secret_key: str,
        *,
        use_case: AdminAuthUseCase | None = None,
    ) -> None:
        super().__init__(secret_key=secret_key)
        self._use_case = use_case

    def _get_use_case(self) -> AdminAuthUseCase:
        return self._use_case or AdminAuthUseCase(
            user_reader=AdminUserReader(get_default_session_factory())
        )

    async def login(self, request: Request) -> bool:
        form = await request.form()
        login_result = await self._get_use_case().login_with_password(
            str(form.get("username", "")),
            str(form.get("password", "")),
        )
        if not login_result:
            return False

        request.session["admin_token"] = login_result.token
        request.session["admin_permissions"] = sorted(login_result.permissions)
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return await self._get_use_case().authenticate_session_token(
            request.session.get("admin_token")
        )
