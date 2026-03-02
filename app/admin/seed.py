"""
Uygulama başlangıcında varsayılan admin kullanıcısını oluşturur.
ADMIN_EMAIL zaten varsa hiçbir şey yapmaz.
"""

from __future__ import annotations

import structlog

from app.core.config import settings
from app.core.security import hash_password
from app.db.models.user import User, UserRole
from app.db.repositories.user import UserRepository
from app.db.session import AsyncSessionFactory

logger = structlog.get_logger(__name__)


async def create_default_admin() -> None:
    async with AsyncSessionFactory() as session:
        repo = UserRepository(session)

        if await repo.email_exists(settings.ADMIN_EMAIL):
            logger.info("admin_already_exists", email=settings.ADMIN_EMAIL)
            return

        admin = User(
            email=settings.ADMIN_EMAIL.lower(),
            hashed_password=hash_password(settings.ADMIN_PASSWORD),
            full_name="Admin",
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
        )
        session.add(admin)
        await session.commit()
        logger.info("default_admin_created", email=settings.ADMIN_EMAIL)
