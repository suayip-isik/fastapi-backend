"""Async session provider yardımcıları.

Global session factory'yi doğrudan servis katmanına taşımamak için
küçük adapter/protocol tanımları sağlar.
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import TYPE_CHECKING, Protocol

from app.db import session as db_session

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession


class AsyncSessionFactoryProtocol(Protocol):
    """AsyncSession context manager üreten callable protocol'ü."""

    def __call__(self, **local_kw: object) -> AbstractAsyncContextManager[AsyncSession]:
        """Yeni bir AsyncSession context manager döndür."""


def get_default_session_factory() -> AsyncSessionFactoryProtocol:
    """Uygulamanın varsayılan async session factory'sini döndür."""
    return db_session.AsyncSessionFactory


@asynccontextmanager
async def session_scope(
    session_factory: AsyncSessionFactoryProtocol,
) -> AsyncIterator[AsyncSession]:
    """Verilen factory ile session açıp güvenli şekilde kapat."""
    async with session_factory() as session:
        yield session
