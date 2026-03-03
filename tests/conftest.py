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
from app.core.limiter import limiter
from app.db.models.base import Base
from app.db.session import get_db
from app.main import app

# Test DB — ayrı bir DB kullan
TEST_DATABASE_URL = settings.DATABASE_URL.replace(
    f"/{settings.POSTGRES_DB}", "/test_db"
)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Test başında tabloları oluştur, sonunda sil (sync — kendi loop'unu kullanır)."""

    async def _create() -> None:
        engine = create_async_engine(TEST_DATABASE_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    async def _drop() -> None:
        engine = create_async_engine(TEST_DATABASE_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(_create())
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
def mock_enqueue():
    """
    Tüm testlerde ARQ enqueue'yu mock'la.
    app.services.auth.enqueue patch'lenir (kullanıldığı yer).
    """
    with patch("app.services.auth.enqueue", new_callable=AsyncMock) as mock:
        yield mock


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Her test için kendi event loop'unda taze engine + session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


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
