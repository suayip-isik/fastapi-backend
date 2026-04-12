"""Superadmin seed unit testleri."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.admin.seed import create_default_app_user, create_default_superadmin, seed_system_roles
from app.core.system_roles import APP_USER_ROLE, PANEL_ADMIN_ROLE
from app.db.models.user import SurfaceType, User


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
    session = _DummySession([None, None])

    with patch("app.admin.seed.get_default_session_factory", return_value=lambda: session):
        roles = await seed_system_roles()

    assert sorted(roles.keys()) == [APP_USER_ROLE, PANEL_ADMIN_ROLE]
    assert session.commit_count == 1
    created_roles = [item for item in session.added if item.__class__.__name__ == "Role"]
    created_permissions = [
        item for item in session.added if item.__class__.__name__ == "RolePermission"
    ]
    assert len(created_roles) == 2
    assert len(created_permissions) > 0


@pytest.mark.asyncio
async def test_seed_system_roles_skips_existing_roles() -> None:
    existing_admin = SimpleNamespace(name=PANEL_ADMIN_ROLE)
    existing_user = SimpleNamespace(name=APP_USER_ROLE)
    session = _DummySession([existing_admin, existing_user])

    with patch("app.admin.seed.get_default_session_factory", return_value=lambda: session):
        roles = await seed_system_roles()

    assert roles == {
        PANEL_ADMIN_ROLE: existing_admin,
        APP_USER_ROLE: existing_user,
    }
    assert session.commit_count == 1
    assert session.added == []


@pytest.mark.asyncio
async def test_create_default_superadmin_returns_if_superadmin_exists() -> None:
    session = _DummySession()

    with (
        patch("app.admin.seed.get_default_session_factory", return_value=lambda: session),
        patch("app.admin.seed.UserRepository.email_exists", new=AsyncMock(return_value=True)),
        patch("app.admin.seed._username_exists", new=AsyncMock(return_value=False)),
    ):
        await create_default_superadmin()

    assert session.added == []
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_create_default_superadmin_returns_if_admin_role_missing() -> None:
    session = _DummySession([None])

    with (
        patch("app.admin.seed.get_default_session_factory", return_value=lambda: session),
        patch("app.admin.seed.UserRepository.email_exists", new=AsyncMock(return_value=False)),
        patch("app.admin.seed._username_exists", new=AsyncMock(return_value=False)),
    ):
        await create_default_superadmin()

    assert session.added == []
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_create_default_superadmin_creates_admin_user() -> None:
    admin_role = SimpleNamespace(id=uuid4(), name=PANEL_ADMIN_ROLE)
    session = _DummySession([admin_role])

    with (
        patch("app.admin.seed.get_default_session_factory", return_value=lambda: session),
        patch("app.admin.seed.UserRepository.email_exists", new=AsyncMock(return_value=False)),
        patch("app.admin.seed._username_exists", new=AsyncMock(return_value=False)),
        patch("app.admin.seed.hash_password", return_value="hashed-pass"),
        patch("app.admin.seed.settings.SUPERADMIN_USERNAME", "superadmin"),
        patch("app.admin.seed.settings.SUPERADMIN_EMAIL", "superadmin@example.com"),
        patch("app.admin.seed.settings.SUPERADMIN_PASSWORD", "StrongPass1"),
    ):
        await create_default_superadmin()

    assert session.commit_count == 1
    assert len(session.added) == 1
    admin = session.added[0]
    assert isinstance(admin, User)
    assert admin.username == "superadmin"
    assert admin.email == "superadmin@example.com"
    assert admin.hashed_password == "hashed-pass"
    assert admin.surface == SurfaceType.ADMIN.value
    assert admin.role_id == admin_role.id


@pytest.mark.asyncio
async def test_create_default_app_user_creates_client_user() -> None:
    app_user_role = SimpleNamespace(id=uuid4(), name=APP_USER_ROLE)
    session = _DummySession([app_user_role])

    with (
        patch("app.admin.seed.get_default_session_factory", return_value=lambda: session),
        patch("app.admin.seed.UserRepository.email_exists", new=AsyncMock(return_value=False)),
        patch("app.admin.seed._username_exists", new=AsyncMock(return_value=False)),
        patch("app.admin.seed.hash_password", return_value="hashed-pass"),
        patch("app.admin.seed.settings.DEFAULT_APP_USER_USERNAME", "suayip"),
        patch("app.admin.seed.settings.DEFAULT_APP_USER_EMAIL", "suayip@example.com"),
        patch("app.admin.seed.settings.DEFAULT_APP_USER_PASSWORD", "StrongPass1"),
    ):
        await create_default_app_user()

    assert session.commit_count == 1
    assert len(session.added) == 1
    app_user = session.added[0]
    assert isinstance(app_user, User)
    assert app_user.username == "suayip"
    assert app_user.email == "suayip@example.com"
    assert app_user.hashed_password == "hashed-pass"
    assert app_user.surface == SurfaceType.CLIENT.value
    assert app_user.role_id == app_user_role.id


@pytest.mark.asyncio
async def test_create_default_app_user_returns_if_username_exists() -> None:
    session = _DummySession()

    with (
        patch("app.admin.seed.get_default_session_factory", return_value=lambda: session),
        patch("app.admin.seed.UserRepository.email_exists", new=AsyncMock(return_value=False)),
        patch("app.admin.seed._username_exists", new=AsyncMock(return_value=True)),
    ):
        await create_default_app_user()

    assert session.added == []
    assert session.commit_count == 0
