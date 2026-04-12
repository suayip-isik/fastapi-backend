"""Canonical sistem rolleri ve varsayılan kullanıcıları seed eder."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.core.config import settings
from app.core.permissions import (
    APP_USER_PERMISSIONS,
    PANEL_ADMIN_PERMISSIONS,
)
from app.core.security import hash_password
from app.core.system_roles import APP_USER_ROLE, PANEL_ADMIN_ROLE
from app.db.models.role import Role, RolePermission
from app.db.models.user import SurfaceType, User
from app.db.repositories.user import UserRepository
from app.db.session_provider import get_default_session_factory

if TYPE_CHECKING:
    from collections.abc import Set

    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

_SYSTEM_ROLES = [
    {
        "name": PANEL_ADMIN_ROLE,
        "description": "Tam yetkili sistem yöneticisi",
        "permissions": PANEL_ADMIN_PERMISSIONS,
    },
    {
        "name": APP_USER_ROLE,
        "description": "Uygulama kullanıcısı",
        "permissions": APP_USER_PERMISSIONS,
    },
]


async def _username_exists(session: AsyncSession, username: str) -> bool:
    from sqlalchemy import select

    result = await session.execute(select(User.id).where(User.username == username))
    return result.scalar_one_or_none() is not None


async def seed_system_roles() -> dict[str, Role]:
    """Sistem rollerini yoksa oluşturur, varsa atlar.

    Returns:
        Dict[str, Role]: role_name → Role nesnesi (tüm sistem rolleri).
    """
    from sqlalchemy import select

    roles: dict[str, Role] = {}

    session_factory = get_default_session_factory()

    async with session_factory() as session:
        for role_data in _SYSTEM_ROLES:
            result = await session.execute(select(Role).where(Role.name == role_data["name"]))
            role = result.scalar_one_or_none()

            if not role:
                role = Role(
                    name=role_data["name"],
                    description=role_data["description"],
                    is_system=True,
                )
                session.add(role)
                await session.flush()

                for perm in role_data["permissions"]:
                    session.add(RolePermission(role_id=role.id, permission=perm))

                await session.flush()
                logger.info("system_role_created", role=role_data["name"])
            else:
                if hasattr(role, "id"):
                    existing_permissions: Set[str] = getattr(role, "permission_set", set())
                    for perm in role_data["permissions"]:
                        if perm not in existing_permissions:
                            session.add(RolePermission(role_id=role.id, permission=perm))
                logger.info("system_role_exists", role=role_data["name"])

            roles[role.name] = role

        await session.commit()

    return roles


async def create_default_superadmin() -> None:
    """Varsayılan `panel_admin` kullanıcısını yoksa oluşturur."""
    if not settings.SUPERADMIN_PASSWORD:
        logger.warning("superadmin_seed_skipped_no_password")
        return

    from sqlalchemy import select

    session_factory = get_default_session_factory()

    async with session_factory() as session:
        user_repo = UserRepository(session)

        if await user_repo.email_exists(settings.SUPERADMIN_EMAIL) or await _username_exists(
            session, settings.SUPERADMIN_USERNAME
        ):
            logger.info(
                "superadmin_already_exists",
                email=settings.SUPERADMIN_EMAIL,
                username=settings.SUPERADMIN_USERNAME,
            )
            return

        result = await session.execute(select(Role).where(Role.name == PANEL_ADMIN_ROLE))
        admin_role = result.scalar_one_or_none()

        if not admin_role:
            logger.error("admin_role_not_found_cannot_create_superadmin")
            return

        superadmin = User(
            email=settings.SUPERADMIN_EMAIL.lower(),
            username=settings.SUPERADMIN_USERNAME,
            hashed_password=hash_password(settings.SUPERADMIN_PASSWORD),
            full_name="Superadmin",
            surface=SurfaceType.ADMIN.value,
            role_id=admin_role.id,
            is_active=True,
            is_verified=True,
        )
        session.add(superadmin)
        await session.commit()
        logger.info("default_superadmin_created", email=settings.SUPERADMIN_EMAIL)


async def create_default_app_user() -> None:
    """Varsayılan `app_user` client kullanıcısını yoksa oluşturur."""
    if not settings.DEFAULT_APP_USER_PASSWORD:
        logger.warning("default_app_user_seed_skipped_no_password")
        return

    from sqlalchemy import select

    session_factory = get_default_session_factory()

    async with session_factory() as session:
        user_repo = UserRepository(session)

        if await user_repo.email_exists(settings.DEFAULT_APP_USER_EMAIL) or await _username_exists(
            session, settings.DEFAULT_APP_USER_USERNAME
        ):
            logger.info(
                "default_app_user_already_exists",
                email=settings.DEFAULT_APP_USER_EMAIL,
                username=settings.DEFAULT_APP_USER_USERNAME,
            )
            return

        result = await session.execute(select(Role).where(Role.name == APP_USER_ROLE))
        app_user_role = result.scalar_one_or_none()

        if not app_user_role:
            logger.error("app_user_role_not_found_cannot_create_default_app_user")
            return

        default_app_user = User(
            email=settings.DEFAULT_APP_USER_EMAIL.lower(),
            username=settings.DEFAULT_APP_USER_USERNAME,
            hashed_password=hash_password(settings.DEFAULT_APP_USER_PASSWORD),
            full_name=settings.DEFAULT_APP_USER_FULL_NAME,
            surface=SurfaceType.CLIENT.value,
            role_id=app_user_role.id,
            is_active=True,
            is_verified=True,
        )
        session.add(default_app_user)
        await session.commit()
        logger.info("default_app_user_created", email=settings.DEFAULT_APP_USER_EMAIL)
