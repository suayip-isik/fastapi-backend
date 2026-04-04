"""
Async PostgreSQL session factory (SQLAlchemy 2.0).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# ── Engine ────────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,  # Stale connection tespiti
    pool_recycle=3600,  # 1 saatte bir connection yenile
    echo=settings.APP_DEBUG,  # SQL logları sadece dev'de
)

# ── Session Factory ───────────────────────────────────────────────────────────
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Commit sonrası lazy-load sorununu önler
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Database session dependency (request scope).

    Her HTTP request için yeni bir AsyncSession oluşturur. Request
    tamamlandığında session otomatik kapanır ve commit/rollback
    işlemleri yönetilir. Transaction yönetimi try/except bloğu
    ile otomatik yapılır (exception durumunda rollback).

    Yields:
        AsyncSession: SQLAlchemy async session instance

    Example:
        >>> @router.get("/users")
        >>> async def get_users(db: DBDep):
        ...     users = await db.execute(select(User))
        ...     return users.scalars().all()
        >>> # Request bitince db.close() otomatik

    Note:
        - Connection pool'dan session alınır (pool_size=10)
        - Exception durumunda rollback otomatik yapılır
        - Başarılı tamamlanmada commit otomatik yapılır
        - expire_on_commit=False (commit sonrası lazy-load sorunsuz)
        - pool_pre_ping=True (stale connection kontrolü aktif)
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
