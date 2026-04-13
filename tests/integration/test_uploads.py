"""Uploads endpoint testleri — /api/v1/shared/uploads/"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import update as sa_update

from app.api.dependencies.infrastructure import get_storage_port
from app.core.exceptions import FileTooLargeError, InvalidFileTypeError
from app.core.permissions import Permission
from app.core.system_roles import PANEL_ADMIN_ROLE
from app.db.models.role import Role, RolePermission
from app.db.models.user import SurfaceType, User
from app.main import app

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

# ── Helpers ───────────────────────────────────────────────────────────────────

_FAKE_KEY = "users/some-uuid/file.jpg"
_FAKE_URL = "http://minio:9000/bucket/users/some-uuid/file.jpg"

_VALID_FILE = ("test.jpg", b"fake-image-bytes", "image/jpeg")
_TEXT_FILE = ("test.txt", b"hello", "text/plain")


async def _auth_headers(client: AsyncClient, email: str, password: str = "StrongPass1") -> dict:
    """Yardımcı fonksiyon."""
    await client.post("/api/v1/client/auth/register", json={"email": email, "password": password})
    res = await client.post(
        "/api/v1/client/auth/login", json={"email": email, "password": password}
    )
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def _get_user_id(client: AsyncClient, headers: dict) -> str:
    """Yardımcı fonksiyon."""
    res = await client.get("/api/v1/shared/me", headers=headers)
    return res.json()["id"]


async def _promote_to_admin(db_session: AsyncSession, email: str) -> None:
    """Yardımcı fonksiyon."""
    from sqlalchemy import select

    result = await db_session.execute(select(Role.id).where(Role.name == PANEL_ADMIN_ROLE))
    admin_role_id = result.scalar_one()
    await db_session.execute(
        sa_update(User)
        .where(User.email == email)
        .values(role_id=admin_role_id, surface=SurfaceType.ADMIN.value)
    )
    await db_session.commit()
    db_session.expire_all()


async def _assign_role_by_name(db_session: AsyncSession, email: str, role_name: str) -> None:
    """Kullanıcıya isme göre rol atar."""
    from sqlalchemy import select

    result = await db_session.execute(select(Role.id).where(Role.name == role_name))
    role_id = result.scalar_one()
    await db_session.execute(sa_update(User).where(User.email == email).values(role_id=role_id))
    await db_session.commit()
    db_session.expire_all()


async def _create_custom_role_with_panel_access(db_session: AsyncSession, role_name: str) -> None:
    """Sadece uploads.delete.any permission'ı taşıyan özel rol oluşturur."""
    role = Role(name=role_name, description="Custom admin access role", is_system=False)
    db_session.add(role)
    await db_session.flush()
    db_session.add(RolePermission(role_id=role.id, permission=Permission.UPLOADS_DELETE_ANY))
    await db_session.commit()
    db_session.expire_all()


def _mock_storage(key: str = _FAKE_KEY, url: str = _FAKE_URL) -> MagicMock:
    """Başarılı upload/delete için mock storage döner."""
    mock = MagicMock()
    mock.upload = AsyncMock(return_value=key)
    mock.get_url = AsyncMock(return_value=url)
    mock.delete = AsyncMock()
    return mock


@contextmanager
def _override_storage(mock: MagicMock):
    app.dependency_overrides[get_storage_port] = lambda: mock
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_storage_port, None)


# ── POST /uploads ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_file_success(client: AsyncClient):
    """test_upload_file_success senaryosunu test eder."""
    headers = await _auth_headers(client, "uploader@example.com")

    with _override_storage(_mock_storage()):
        res = await client.post(
            "/api/v1/shared/uploads",
            headers=headers,
            files={"file": _VALID_FILE},
        )

    assert res.status_code == 200
    data = res.json()
    assert data["key"] == _FAKE_KEY
    assert data["url"] == _FAKE_URL
    assert "message" in data


@pytest.mark.asyncio
async def test_upload_file_unauthorized(client: AsyncClient):
    """test_upload_file_unauthorized senaryosunu test eder."""
    with _override_storage(_mock_storage()):
        res = await client.post(
            "/api/v1/shared/uploads",
            files={"file": _VALID_FILE},
        )

    assert res.status_code == 401


@pytest.mark.asyncio
async def test_upload_file_too_large(client: AsyncClient):
    """test_upload_file_too_large senaryosunu test eder."""
    headers = await _auth_headers(client, "uploader_large@example.com")

    mock = _mock_storage()
    mock.upload = AsyncMock(side_effect=FileTooLargeError())

    with _override_storage(mock):
        res = await client.post(
            "/api/v1/shared/uploads",
            headers=headers,
            files={"file": _VALID_FILE},
        )

    assert res.status_code == 413


@pytest.mark.asyncio
async def test_upload_file_invalid_type(client: AsyncClient):
    """test_upload_file_invalid_type senaryosunu test eder."""
    headers = await _auth_headers(client, "uploader_type@example.com")

    mock = _mock_storage()
    mock.upload = AsyncMock(side_effect=InvalidFileTypeError())

    with _override_storage(mock):
        res = await client.post(
            "/api/v1/shared/uploads",
            headers=headers,
            files={"file": _TEXT_FILE},
        )

    assert res.status_code == 415


@pytest.mark.asyncio
async def test_upload_calls_storage_with_user_folder(client: AsyncClient):
    """Storage.upload kullanıcıya özgü klasör ile çağrılmalı."""
    headers = await _auth_headers(client, "uploader_folder@example.com")
    user_id = await _get_user_id(client, headers)

    mock = _mock_storage()

    with _override_storage(mock):
        await client.post(
            "/api/v1/shared/uploads",
            headers=headers,
            files={"file": _VALID_FILE},
        )

    mock.upload.assert_called_once()
    call_kwargs = mock.upload.call_args
    folder_arg = call_kwargs.kwargs.get("folder") or call_kwargs.args[1]
    assert user_id in folder_arg


# ── DELETE /uploads ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_file_as_owner(client: AsyncClient):
    """test_delete_file_as_owner senaryosunu test eder."""
    headers = await _auth_headers(client, "owner_del@example.com")
    user_id = await _get_user_id(client, headers)
    key = f"users/{user_id}/myfile.jpg"

    mock = _mock_storage()

    with _override_storage(mock):
        res = await client.delete(f"/api/v1/shared/uploads?key={key}", headers=headers)

    assert res.status_code == 200
    mock.delete.assert_called_once_with(key)


@pytest.mark.asyncio
async def test_delete_file_not_owner(client: AsyncClient):
    """Başkasının dosyasını silmeye çalışmak 403 dönmeli."""
    headers = await _auth_headers(client, "not_owner_del@example.com")
    other_key = "users/00000000-0000-0000-0000-000000000000/file.jpg"

    mock = _mock_storage()

    with _override_storage(mock):
        res = await client.delete(f"/api/v1/shared/uploads?key={other_key}", headers=headers)

    assert res.status_code == 403
    mock.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_file_as_admin(client: AsyncClient, db_session: AsyncSession):
    """Admin başkasının dosyasını silebilmeli."""
    admin_email = "admin_del@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    other_key = "users/00000000-0000-0000-0000-000000000000/anyfile.jpg"
    mock = _mock_storage()

    with _override_storage(mock):
        res = await client.delete(f"/api/v1/shared/uploads?key={other_key}", headers=headers)

    assert res.status_code == 200
    mock.delete.assert_called_once_with(other_key)


@pytest.mark.asyncio
async def test_delete_file_with_custom_admin_access_role(
    client: AsyncClient, db_session: AsyncSession
):
    """Admin surface + uploads.delete.any taşıyan özel rol de başkasının dosyasını silebilmeli."""
    email = "custom_admin_access_del@example.com"
    headers = await _auth_headers(client, email)
    await _promote_to_admin(db_session, email)
    await _create_custom_role_with_panel_access(db_session, "file_admin")
    await _assign_role_by_name(db_session, email, "file_admin")

    other_key = "users/00000000-0000-0000-0000-000000000000/anyfile.jpg"
    mock = _mock_storage()

    with _override_storage(mock):
        res = await client.delete(f"/api/v1/shared/uploads?key={other_key}", headers=headers)

    assert res.status_code == 200
    mock.delete.assert_called_once_with(other_key)


@pytest.mark.asyncio
async def test_delete_file_unauthorized(client: AsyncClient):
    """test_delete_file_unauthorized senaryosunu test eder."""
    mock = _mock_storage()

    with _override_storage(mock):
        res = await client.delete("/api/v1/shared/uploads?key=users/some-id/file.jpg")

    assert res.status_code == 401
    mock.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_file_missing_key_param(client: AsyncClient):
    """key query param olmadan DELETE isteği 422 dönmeli."""
    headers = await _auth_headers(client, "del_nokey@example.com")

    with _override_storage(_mock_storage()):
        res = await client.delete("/api/v1/shared/uploads", headers=headers)

    assert res.status_code == 422


@pytest.mark.asyncio
async def test_upload_no_file_field(client: AsyncClient):
    """file field'ı olmadan POST /uploads → 422."""
    headers = await _auth_headers(client, "nofile@example.com")

    with _override_storage(_mock_storage()):
        res = await client.post("/api/v1/shared/uploads", headers=headers)

    assert res.status_code == 422
