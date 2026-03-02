"""
Pytest fixtures — async test altyapısı.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import fakeredis.aioredis as fakeredis_aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.core.redis as redis_module
from app.core.config import settings
from app.db.models.base import Base
from app.db.session import get_db
from app.main import app

# Test DB — ayrı bir DB kullan
TEST_DATABASE_URL = settings.DATABASE_URL.replace(
    f"/{settings.POSTGRES_DB}", "/test_db"
)

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionFactory = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    """Test başında tabloları oluştur, sonunda sil."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def fake_redis():
    """
    Tüm testlerde gerçek Redis yerine fakeredis kullan.
    app.core.redis singleton'ı FakeRedis instance'ı ile override edilir.
    """
    fake = fakeredis_aioredis.FakeRedis(decode_responses=True)
    redis_module._redis_client = fake
    yield fake
    await fake.aclose()
    redis_module._redis_client = None


@pytest.fixture(autouse=True)
def mock_enqueue():
    """
    Tüm testlerde ARQ enqueue'yu mock'la.
    app.services.auth.enqueue patch'lenir (kullanıldığı yer).
    """
    with patch("app.services.auth.enqueue", new_callable=AsyncMock) as mock:
        yield mock


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Her test için transaction + rollback."""
    async with test_engine.begin() as conn:
        async with TestSessionFactory(bind=conn) as session:
            yield session
            await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Test HTTP client — DB override ile."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
