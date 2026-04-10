"""Admin seed unit testleri."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.admin.seed import create_default_admin, seed_system_roles
from app.db.models.user import AccountType, User


class _DummyExecuteResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _DummySession:
    def __init__(self, execute_values: list[object | None] | None = None):
        self.execute_values = list(execute_values or [])
        self.added: list[object] = []
        self.flush_count = 0
        self.commit_count = 0

    async def __aenter__(self) -> _DummySession:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def execute(self, stmt):
        value = self.execute_values.pop(0) if self.execute_values else None
        return _DummyExecuteResult(value)

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flush_count += 1

    async def commit(self) -> None:
        self.commit_count += 1


@pytest.mark.asyncio
async def test_seed_system_roles_creates_missing_roles() -> None:
    session = _DummySession([None, None, None])

    with patch("app.admin.seed.get_default_session_factory", return_value=lambda: session):
        roles = await seed_system_roles()

    assert sorted(roles.keys()) == ["admin", "moderator", "user"]
    assert session.commit_count == 1
    created_roles = [item for item in session.added if item.__class__.__name__ == "Role"]
    created_permissions = [
        item for item in session.added if item.__class__.__name__ == "RolePermission"
    ]
    assert len(created_roles) == 3
    assert len(created_permissions) > 0


@pytest.mark.asyncio
async def test_seed_system_roles_skips_existing_roles() -> None:
    existing_admin = SimpleNamespace(name="admin")
    existing_user = SimpleNamespace(name="user")
    existing_moderator = SimpleNamespace(name="moderator")
    session = _DummySession([existing_admin, existing_user, existing_moderator])

    with patch("app.admin.seed.get_default_session_factory", return_value=lambda: session):
        roles = await seed_system_roles()

    assert roles == {
        "admin": existing_admin,
        "user": existing_user,
        "moderator": existing_moderator,
    }
    assert session.commit_count == 1
    assert session.added == []


@pytest.mark.asyncio
async def test_create_default_admin_returns_if_admin_exists() -> None:
    session = _DummySession()

    with (
        patch("app.admin.seed.get_default_session_factory", return_value=lambda: session),
        patch("app.admin.seed.UserRepository.email_exists", new=AsyncMock(return_value=True)),
    ):
        await create_default_admin()

    assert session.added == []
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_create_default_admin_returns_if_admin_role_missing() -> None:
    session = _DummySession([None])

    with (
        patch("app.admin.seed.get_default_session_factory", return_value=lambda: session),
        patch("app.admin.seed.UserRepository.email_exists", new=AsyncMock(return_value=False)),
    ):
        await create_default_admin()

    assert session.added == []
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_create_default_admin_creates_admin_user() -> None:
    admin_role = SimpleNamespace(id=uuid4(), name="admin")
    session = _DummySession([admin_role])

    with (
        patch("app.admin.seed.get_default_session_factory", return_value=lambda: session),
        patch("app.admin.seed.UserRepository.email_exists", new=AsyncMock(return_value=False)),
        patch("app.admin.seed.hash_password", return_value="hashed-pass"),
        patch("app.admin.seed.settings.ADMIN_EMAIL", "admin@example.com"),
        patch("app.admin.seed.settings.ADMIN_PASSWORD", "StrongPass1"),
    ):
        await create_default_admin()

    assert session.commit_count == 1
    assert len(session.added) == 1
    admin = session.added[0]
    assert isinstance(admin, User)
    assert admin.email == "admin@example.com"
    assert admin.hashed_password == "hashed-pass"
    assert admin.account_type == AccountType.ADMIN.value
    assert admin.role_id == admin_role.id
