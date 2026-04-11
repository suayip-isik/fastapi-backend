"""
Pytest fixtures — async test altyapısı.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import fakeredis.aioredis as fakeredis_aioredis
import pytest
import pytest_asyncio
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.core.redis as redis_module
from app.core.config import settings
from app.core.limiter import limiter
from app.core.permissions import ADMIN_PERMISSIONS, MODERATOR_PERMISSIONS, USER_PERMISSIONS
from app.db.models.base import Base
from app.db.models.role import Role, RolePermission
from app.db.session import get_db
from app.main import app

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# Test DB — ayrı bir DB kullan
TEST_DATABASE_URL = settings.DATABASE_URL.replace(f"/{settings.POSTGRES_DB}", "/test_db")

# NullPool session factory — test süresi boyunca app engine'ini override eder
_null_pool_factory = async_sessionmaker(
    create_async_engine(TEST_DATABASE_URL, poolclass=NullPool),
    expire_on_commit=False,
)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Test başında tabloları oluştur, sonunda sil.

    NullPool kullanır: event loop sınırı aşılmaz, connection havuzu taşmaz.
    """

    async def _create() -> None:
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    async def _drop() -> None:
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(_create())

    # App engine'i NullPool ile override et — provider getter'ları bu factory'yi kullanır
    with patch("app.db.session.AsyncSessionFactory", _null_pool_factory):
        yield

    asyncio.run(_drop())


@pytest_asyncio.fixture(autouse=True)
async def fake_redis():
    """
    Tüm testlerde gerçek Redis yerine fakeredis kullan.
    app.core.redis singleton'ı FakeRedis instance'ı ile override edilir.
    """
    fake = fakeredis_aioredis.FakeRedis(decode_responses=True)
    redis_module._redis_client = fake
    yield fake
    await fake.close()
    redis_module._redis_client = None


@pytest.fixture(autouse=True)
def disable_rate_limits():
    """Test süresince rate limiting'i devre dışı bırak."""
    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture(autouse=True)
def disable_schema_guard():
    """Test DB create_all kullandığı için startup schema guard'ını kapat."""
    original = settings.ENFORCE_DB_SCHEMA_CHECK
    settings.ENFORCE_DB_SCHEMA_CHECK = False
    yield
    settings.ENFORCE_DB_SCHEMA_CHECK = original


@pytest.fixture(autouse=True)
def mock_enqueue():
    """
    Tüm testlerde ARQ enqueue'yu mock'la.
    Clean architecture refactor sonrası queue adapter'ı
    `app.adapters.infrastructure.enqueue` üstünden çalışır.
    """
    mock = AsyncMock()
    with (
        patch("app.adapters.infrastructure.enqueue", mock),
        patch("app.tasks.worker.enqueue", mock),
    ):
        yield mock


@pytest.fixture(autouse=True)
def mock_audit_log():
    """
    Tüm testlerde AuditService.log'u mock'la.

    AuditService bağımsız bir session provider üzerinden ayrı session açar ve henüz
    commit edilmemiş user_id'ye FK referans içeren bir INSERT yapar. Bu,
    PostgreSQL'in işlem kilidini beklemesine neden olur (transactionid wait).
    Ana session (db_session) commit edilmeden önce AuditService'in bu INSERT'i
    beklediği için kilitlenme (deadlock) oluşur.

    test_audit_log.py zaten AuditableMixin._audit_log'u mock'ladığından
    bu fixture ile çakışmaz.
    """
    with patch("app.services.audit.AuditService.log", new_callable=AsyncMock) as mock:
        yield mock


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Her test için NullPool engine + taze session.

    NullPool: her bağlantı işlem sonrası hemen kapatılır.
    Test öncesi tüm tablolar temizlenir — izolasyon sağlanır.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()

        for role_data in [
            {"name": "admin", "description": "Admin", "permissions": ADMIN_PERMISSIONS},
            {"name": "user", "description": "User", "permissions": USER_PERMISSIONS},
            {"name": "moderator", "description": "Moderator", "permissions": MODERATOR_PERMISSIONS},
        ]:
            role = Role(
                name=role_data["name"], description=role_data["description"], is_system=True
            )
            session.add(role)
            await session.flush()
            for perm in role_data["permissions"]:
                session.add(RolePermission(role_id=role.id, permission=perm))
        await session.commit()

        try:
            yield session
        finally:
            await session.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Test HTTP client — DB override ile."""

    async def override_get_db():
        """override_get_db işlemini gerçekleştirir."""
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
