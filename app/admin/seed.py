"""
Uygulama başlangıcında sistem rolleri ve varsayılan admin kullanıcısını oluşturur.
İdempotent: mevcut kayıtlar varsa atlanır.
"""

from __future__ import annotations

import structlog

from app.core.config import settings
from app.core.permissions import (
    ADMIN_PERMISSIONS,
    MODERATOR_PERMISSIONS,
    USER_PERMISSIONS,
)
from app.core.security import hash_password
from app.db.models.role import Role, RolePermission
from app.db.models.user import AccountType, User
from app.db.repositories.user import UserRepository
from app.db.session_provider import get_default_session_factory

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
                logger.info("system_role_exists", role=role_data["name"])

            roles[role.name] = role

        await session.commit()

    return roles


async def create_default_admin() -> None:
    """Varsayılan admin kullanıcısını yoksa oluşturur.

    Sistem rolleri seed edilmiş olmalıdır (seed_system_roles çağrısı önceden yapılmalı).
    """
    from sqlalchemy import select

    session_factory = get_default_session_factory()

    async with session_factory() as session:
        user_repo = UserRepository(session)

        if await user_repo.email_exists(settings.ADMIN_EMAIL):
            logger.info("admin_already_exists", email=settings.ADMIN_EMAIL)
            return

        result = await session.execute(select(Role).where(Role.name == "admin"))
        admin_role = result.scalar_one_or_none()

        if not admin_role:
            logger.error("admin_role_not_found_cannot_create_admin")
            return

        admin = User(
            email=settings.ADMIN_EMAIL.lower(),
            hashed_password=hash_password(settings.ADMIN_PASSWORD),
            full_name="Admin",
            account_type=AccountType.ADMIN.value,
            role_id=admin_role.id,
            is_active=True,
            is_verified=True,
        )
        session.add(admin)
        await session.commit()
        logger.info("default_admin_created", email=settings.ADMIN_EMAIL)
