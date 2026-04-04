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
    """Varsayılan admin kullanıcısını yoksa oluşturur.

    Uygulama başlangıcında çağrılır. ADMIN_EMAIL ve ADMIN_PASSWORD
    ayarlarından faydalanarak tam yetkili bir admin hesabı oluşturur.

    İş mantığı:
        1. ADMIN_EMAIL adresinin veritabanında mevcut olup olmadığını kontrol eder.
        2. Kayıt varsa işlem yapmadan döner (idempotent).
        3. Kayıt yoksa şifreyi bcrypt ile hash'ler ve kullanıcıyı oluşturur.
        4. Kullanıcı is_active=True, is_verified=True, role=ADMIN olarak kaydedilir.

    Raises:
        SQLAlchemyError: Veritabanı bağlantısı veya commit işlemi başarısız olursa.

    Note:
        - Bu fonksiyon idempotent'tir; birden fazla kez çağrılması güvenlidir.
        - ADMIN_EMAIL ve ADMIN_PASSWORD değerleri `.env` dosyasından okunur.
    """
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
