"""Uploads endpoint testleri — /api/v1/uploads/"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import FileTooLargeError, InvalidFileTypeError
from app.db.models.user import User, UserRole

# ── Helpers ───────────────────────────────────────────────────────────────────

_FAKE_KEY = "users/some-uuid/file.jpg"
_FAKE_URL = "http://minio:9000/bucket/users/some-uuid/file.jpg"

_VALID_FILE = ("test.jpg", b"fake-image-bytes", "image/jpeg")
_TEXT_FILE = ("test.txt", b"hello", "text/plain")


async def _auth_headers(client: AsyncClient, email: str, password: str = "StrongPass1") -> dict:
    await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def _get_user_id(client: AsyncClient, headers: dict) -> str:
    res = await client.get("/api/v1/users/me", headers=headers)
    return res.json()["id"]


async def _promote_to_admin(db_session: AsyncSession, email: str) -> None:
    await db_session.execute(
        sa_update(User).where(User.email == email).values(role=UserRole.ADMIN)
    )
    db_session.expire_all()


def _mock_storage(key: str = _FAKE_KEY, url: str = _FAKE_URL) -> MagicMock:
    """Başarılı upload/delete için mock storage döner."""
    mock = MagicMock()
    mock.upload = AsyncMock(return_value=key)
    mock.get_url = AsyncMock(return_value=url)
    mock.delete = AsyncMock()
    return mock


# ── POST /uploads ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_file_success(client: AsyncClient):
    headers = await _auth_headers(client, "uploader@example.com")

    with patch("app.api.v1.endpoints.uploads.storage", _mock_storage()):
        res = await client.post(
            "/api/v1/uploads",
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
    with patch("app.api.v1.endpoints.uploads.storage", _mock_storage()):
        res = await client.post(
            "/api/v1/uploads",
            files={"file": _VALID_FILE},
        )

    assert res.status_code == 401


@pytest.mark.asyncio
async def test_upload_file_too_large(client: AsyncClient):
    headers = await _auth_headers(client, "uploader_large@example.com")

    mock = _mock_storage()
    mock.upload = AsyncMock(side_effect=FileTooLargeError())

    with patch("app.api.v1.endpoints.uploads.storage", mock):
        res = await client.post(
            "/api/v1/uploads",
            headers=headers,
            files={"file": _VALID_FILE},
        )

    assert res.status_code == 413


@pytest.mark.asyncio
async def test_upload_file_invalid_type(client: AsyncClient):
    headers = await _auth_headers(client, "uploader_type@example.com")

    mock = _mock_storage()
    mock.upload = AsyncMock(side_effect=InvalidFileTypeError())

    with patch("app.api.v1.endpoints.uploads.storage", mock):
        res = await client.post(
            "/api/v1/uploads",
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

    with patch("app.api.v1.endpoints.uploads.storage", mock):
        await client.post(
            "/api/v1/uploads",
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
    headers = await _auth_headers(client, "owner_del@example.com")
    user_id = await _get_user_id(client, headers)
    key = f"users/{user_id}/myfile.jpg"

    mock = _mock_storage()

    with patch("app.api.v1.endpoints.uploads.storage", mock):
        res = await client.delete(f"/api/v1/uploads?key={key}", headers=headers)

    assert res.status_code == 200
    mock.delete.assert_called_once_with(key)


@pytest.mark.asyncio
async def test_delete_file_not_owner(client: AsyncClient):
    """Başkasının dosyasını silmeye çalışmak 403 dönmeli."""
    headers = await _auth_headers(client, "not_owner_del@example.com")
    other_key = "users/00000000-0000-0000-0000-000000000000/file.jpg"

    mock = _mock_storage()

    with patch("app.api.v1.endpoints.uploads.storage", mock):
        res = await client.delete(f"/api/v1/uploads?key={other_key}", headers=headers)

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

    with patch("app.api.v1.endpoints.uploads.storage", mock):
        res = await client.delete(f"/api/v1/uploads?key={other_key}", headers=headers)

    assert res.status_code == 200
    mock.delete.assert_called_once_with(other_key)


@pytest.mark.asyncio
async def test_delete_file_unauthorized(client: AsyncClient):
    mock = _mock_storage()

    with patch("app.api.v1.endpoints.uploads.storage", mock):
        res = await client.delete("/api/v1/uploads?key=users/some-id/file.jpg")

    assert res.status_code == 401
    mock.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_file_missing_key_param(client: AsyncClient):
    """key query param olmadan DELETE isteği 422 dönmeli."""
    headers = await _auth_headers(client, "del_nokey@example.com")

    with patch("app.api.v1.endpoints.uploads.storage", _mock_storage()):
        res = await client.delete("/api/v1/uploads", headers=headers)

    assert res.status_code == 422
