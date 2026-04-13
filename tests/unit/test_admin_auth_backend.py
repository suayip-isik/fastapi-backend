"""Admin auth use-case ve backend davranış testleri."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.admin.auth import AdminAuthBackend, AdminAuthUseCase
from app.core.exceptions import InvalidTokenError
from app.core.permissions import Permission
from app.core.security import TokenType
from app.db.models.user import SurfaceType


class _DummyRequest:
    def __init__(
        self, *, session: dict[str, object] | None = None, form_data: dict[str, str] | None = None
    ):
        self.session = session or {}
        self._form_data = form_data or {}

    async def form(self) -> dict[str, str]:
        return self._form_data


def _user(*, surface: SurfaceType = SurfaceType.ADMIN, is_active: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        hashed_password="hashed",
        surface=surface.value,
        is_active=is_active,
        session_revoked_after=None,
    )


@pytest.mark.asyncio
async def test_login_rejects_empty_credentials() -> None:
    request = _DummyRequest(session={}, form_data={"username": "", "password": ""})
    use_case = AdminAuthUseCase(user_reader=AsyncMock(), permission_provider=AsyncMock())
    backend = AdminAuthBackend(secret_key="test", use_case=use_case)

    assert await backend.login(request) is False


@pytest.mark.asyncio
async def test_login_succeeds_for_admin_account_with_panel_permission() -> None:
    user = _user()
    request = _DummyRequest(
        session={},
        form_data={"username": "admin@example.com", "password": "StrongPass1"},
    )
    user_reader = AsyncMock()
    user_reader.get_active_by_email.return_value = user
    permission_provider = AsyncMock()
    permission_provider.get_permissions.return_value = {Permission.USERS_LIST.value}
    use_case = AdminAuthUseCase(user_reader=user_reader, permission_provider=permission_provider)
    backend = AdminAuthBackend(secret_key="test", use_case=use_case)

    with (
        patch("app.admin.auth.verify_password", return_value=True),
        patch("app.admin.auth.create_access_token", return_value="token-123"),
    ):
        assert await backend.login(request) is True

    assert request.session["admin_token"] == "token-123"


@pytest.mark.asyncio
async def test_login_rejects_client_surface() -> None:
    user = _user(surface=SurfaceType.CLIENT)
    request = _DummyRequest(
        session={},
        form_data={"username": "client@example.com", "password": "StrongPass1"},
    )
    user_reader = AsyncMock()
    user_reader.get_active_by_email.return_value = user
    use_case = AdminAuthUseCase(user_reader=user_reader, permission_provider=AsyncMock())
    backend = AdminAuthBackend(secret_key="test", use_case=use_case)

    with patch("app.admin.auth.verify_password", return_value=True):
        assert await backend.login(request) is False


@pytest.mark.asyncio
async def test_login_rejects_missing_panel_permission() -> None:
    user = _user()
    request = _DummyRequest(
        session={},
        form_data={"username": "admin@example.com", "password": "StrongPass1"},
    )
    user_reader = AsyncMock()
    user_reader.get_active_by_email.return_value = user
    permission_provider = AsyncMock()
    permission_provider.get_permissions.return_value = {"profile.read.self"}
    use_case = AdminAuthUseCase(user_reader=user_reader, permission_provider=permission_provider)
    backend = AdminAuthBackend(secret_key="test", use_case=use_case)

    with patch("app.admin.auth.verify_password", return_value=True):
        assert await backend.login(request) is False


@pytest.mark.asyncio
async def test_login_rejects_invalid_password() -> None:
    user = _user()
    request = _DummyRequest(
        session={},
        form_data={"username": "admin@example.com", "password": "wrong"},
    )
    user_reader = AsyncMock()
    user_reader.get_active_by_email.return_value = user
    use_case = AdminAuthUseCase(user_reader=user_reader, permission_provider=AsyncMock())
    backend = AdminAuthBackend(secret_key="test", use_case=use_case)

    with patch("app.admin.auth.verify_password", return_value=False):
        assert await backend.login(request) is False


@pytest.mark.asyncio
async def test_authenticate_accepts_admin_account_with_panel_permission() -> None:
    user = _user()
    request = _DummyRequest(session={"admin_token": "token-123"})
    payload = SimpleNamespace(
        sub=str(user.id),
        type="access",
        jti="jti-123",
        iat=datetime.now(UTC),
    )
    user_reader = AsyncMock()
    user_reader.get_by_id.return_value = user
    permission_provider = AsyncMock()
    permission_provider.get_permissions.return_value = {Permission.USERS_LIST.value}
    redis = AsyncMock()
    redis.exists.return_value = False
    use_case = AdminAuthUseCase(
        user_reader=user_reader,
        permission_provider=permission_provider,
        redis=redis,
    )
    backend = AdminAuthBackend(secret_key="test", use_case=use_case)

    with patch("app.admin.auth.decode_token", return_value=payload):
        assert await backend.authenticate(request) is True


@pytest.mark.asyncio
async def test_authenticate_rejects_client_surface() -> None:
    user = _user(surface=SurfaceType.CLIENT)
    request = _DummyRequest(session={"admin_token": "token-123"})
    payload = SimpleNamespace(
        sub=str(user.id),
        type="access",
        jti="jti-123",
        iat=datetime.now(UTC),
    )
    user_reader = AsyncMock()
    user_reader.get_by_id.return_value = user
    redis = AsyncMock()
    redis.exists.return_value = False
    use_case = AdminAuthUseCase(
        user_reader=user_reader, permission_provider=AsyncMock(), redis=redis
    )
    backend = AdminAuthBackend(secret_key="test", use_case=use_case)

    with patch("app.admin.auth.decode_token", return_value=payload):
        assert await backend.authenticate(request) is False


@pytest.mark.asyncio
async def test_authenticate_rejects_missing_session_token() -> None:
    backend = AdminAuthBackend(
        secret_key="test",
        use_case=AdminAuthUseCase(user_reader=AsyncMock(), permission_provider=AsyncMock()),
    )
    request = _DummyRequest(session={})

    assert await backend.authenticate(request) is False


@pytest.mark.asyncio
async def test_authenticate_rejects_inactive_admin_user() -> None:
    user = _user(is_active=False)
    request = _DummyRequest(session={"admin_token": "token-123"})
    payload = SimpleNamespace(
        sub=str(user.id),
        type="access",
        jti="jti-123",
        iat=datetime.now(UTC),
    )
    user_reader = AsyncMock()
    user_reader.get_by_id.return_value = user
    redis = AsyncMock()
    redis.exists.return_value = False
    use_case = AdminAuthUseCase(
        user_reader=user_reader, permission_provider=AsyncMock(), redis=redis
    )
    backend = AdminAuthBackend(secret_key="test", use_case=use_case)

    with patch("app.admin.auth.decode_token", return_value=payload):
        assert await backend.authenticate(request) is False


@pytest.mark.asyncio
async def test_authenticate_rejects_wrong_token_type() -> None:
    user = _user()
    request = _DummyRequest(session={"admin_token": "token-123"})
    payload = SimpleNamespace(
        sub=str(user.id),
        type=TokenType.REFRESH,
        jti="jti-123",
        iat=datetime.now(UTC),
    )
    backend = AdminAuthBackend(
        secret_key="test",
        use_case=AdminAuthUseCase(user_reader=AsyncMock(), permission_provider=AsyncMock()),
    )

    with patch("app.admin.auth.decode_token", return_value=payload):
        assert await backend.authenticate(request) is False


@pytest.mark.asyncio
async def test_authenticate_rejects_app_error() -> None:
    request = _DummyRequest(session={"admin_token": "token-123"})
    backend = AdminAuthBackend(
        secret_key="test",
        use_case=AdminAuthUseCase(user_reader=AsyncMock(), permission_provider=AsyncMock()),
    )

    with patch("app.admin.auth.decode_token", side_effect=InvalidTokenError("bad token")):
        assert await backend.authenticate(request) is False


@pytest.mark.asyncio
async def test_authenticate_rejects_blacklisted_token() -> None:
    user = _user()
    request = _DummyRequest(session={"admin_token": "token-123"})
    payload = SimpleNamespace(
        sub=str(user.id),
        type=TokenType.ACCESS,
        jti="jti-123",
        iat=datetime.now(UTC),
    )
    user_reader = AsyncMock()
    redis = AsyncMock()
    redis.exists.return_value = True
    use_case = AdminAuthUseCase(
        user_reader=user_reader, permission_provider=AsyncMock(), redis=redis
    )
    backend = AdminAuthBackend(secret_key="test", use_case=use_case)

    with patch("app.admin.auth.decode_token", return_value=payload):
        assert await backend.authenticate(request) is False


@pytest.mark.asyncio
async def test_authenticate_rejects_token_older_than_session_cutoff() -> None:
    user = _user()
    user.session_revoked_after = datetime.now(UTC)
    request = _DummyRequest(session={"admin_token": "token-123"})
    payload = SimpleNamespace(
        sub=str(user.id),
        type=TokenType.ACCESS,
        jti="jti-123",
        iat=user.session_revoked_after - timedelta(seconds=1),
    )
    user_reader = AsyncMock()
    user_reader.get_by_id.return_value = user
    permission_provider = AsyncMock()
    permission_provider.get_permissions.return_value = {Permission.USERS_LIST.value}
    redis = AsyncMock()
    redis.exists.return_value = False
    use_case = AdminAuthUseCase(
        user_reader=user_reader,
        permission_provider=permission_provider,
        redis=redis,
    )
    backend = AdminAuthBackend(secret_key="test", use_case=use_case)

    with patch("app.admin.auth.decode_token", return_value=payload):
        assert await backend.authenticate(request) is False


@pytest.mark.asyncio
async def test_logout_clears_session() -> None:
    backend = AdminAuthBackend(
        secret_key="test",
        use_case=AdminAuthUseCase(user_reader=AsyncMock(), permission_provider=AsyncMock()),
    )
    request = _DummyRequest(session={"admin_token": "token-123", "other": "value"})

    assert await backend.logout(request) is True
    assert request.session == {}
