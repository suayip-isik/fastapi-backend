"""
Uygulama başlangıcında sistem rolleri ve varsayılan superadmin kullanıcısını oluşturur.
İdempotent: mevcut kayıtlar varsa atlanır.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.core.config import settings
from app.core.permissions import (
    ADMIN_PERMISSIONS,
    MODERATOR_PERMISSIONS,
    USER_PERMISSIONS,
)
from app.core.security import hash_password
from app.db.models.role import Role, RolePermission
from app.db.models.user import SurfaceType, User
from app.db.repositories.user import UserRepository
from app.db.session_provider import get_default_session_factory

if TYPE_CHECKING:
    from collections.abc import Set

logger = structlog.get_logger(__name__)

_SYSTEM_ROLES = [
    {
        "name": "admin",
        "description": "Tam yetkili sistem yöneticisi",
        "permissions": ADMIN_PERMISSIONS,
    },
    {
        "name": "user",
        "description": "Standart kullanıcı",
        "permissions": USER_PERMISSIONS,
    },
    {
        "name": "moderator",
        "description": "İçerik moderatörü",
        "permissions": MODERATOR_PERMISSIONS,
    },
]


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
    """Varsayılan superadmin kullanıcısını yoksa oluşturur.

    Sistem rolleri seed edilmiş olmalıdır (seed_system_roles çağrısı önceden yapılmalı).
    """
    from sqlalchemy import select

    session_factory = get_default_session_factory()

    async with session_factory() as session:
        user_repo = UserRepository(session)

        if await user_repo.email_exists(settings.SUPERADMIN_EMAIL):
            logger.info("superadmin_already_exists", email=settings.SUPERADMIN_EMAIL)
            return

        result = await session.execute(select(Role).where(Role.name == "admin"))
        admin_role = result.scalar_one_or_none()

        if not admin_role:
            logger.error("admin_role_not_found_cannot_create_superadmin")
            return

        superadmin = User(
            email=settings.SUPERADMIN_EMAIL.lower(),
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


async def create_default_admin() -> None:
    """Geriye dönük uyumluluk için varsayılan superadmin oluşturur."""
    await create_default_superadmin()
