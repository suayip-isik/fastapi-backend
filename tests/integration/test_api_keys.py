"""API Keys endpoint testleri — /api/v1/api-keys"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _register_and_login(
    client: AsyncClient, email: str, password: str = "StrongPass1"
) -> dict:
    await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return res.json()


async def _auth_headers(client: AsyncClient, email: str, password: str = "StrongPass1") -> dict:
    tokens = await _register_and_login(client, email, password)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _create_key(
    client: AsyncClient,
    headers: dict,
    name: str = "Test Key",
    scopes: list[str] | None = None,
    expires_at: str | None = None,
) -> dict:
    payload: dict = {"name": name, "scopes": scopes or []}
    if expires_at:
        payload["expires_at"] = expires_at
    res = await client.post("/api/v1/api-keys", json=payload, headers=headers)
    return res.json()


# ── POST /api-keys ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_api_key_success(client: AsyncClient):
    """API key başarıyla oluşturulmalı ve ham key döndürülmeli."""
    headers = await _auth_headers(client, "apikey_create@example.com")

    res = await client.post(
        "/api/v1/api-keys",
        json={"name": "Production Key", "scopes": ["read", "write"]},
        headers=headers,
    )

    assert res.status_code == 201
    data = res.json()
    assert "key" in data
    assert data["key"].startswith("sk_live_")
    assert data["name"] == "Production Key"
    assert "read" in data["scopes"]
    assert "write" in data["scopes"]
    assert "key_prefix" in data
    assert "message" in data


@pytest.mark.asyncio
async def test_create_api_key_without_scopes(client: AsyncClient):
    """Scope olmadan API key oluşturulabilmeli."""
    headers = await _auth_headers(client, "apikey_noscope@example.com")

    res = await client.post(
        "/api/v1/api-keys",
        json={"name": "No Scope Key"},
        headers=headers,
    )

    assert res.status_code == 201
    assert res.json()["scopes"] == []


@pytest.mark.asyncio
async def test_create_api_key_with_expiration(client: AsyncClient):
    """Geçerlilik tarihi ile API key oluşturulabilmeli."""
    headers = await _auth_headers(client, "apikey_expires@example.com")
    expires = (datetime.now(UTC) + timedelta(days=30)).isoformat()

    res = await client.post(
        "/api/v1/api-keys",
        json={"name": "Expiring Key", "expires_at": expires},
        headers=headers,
    )

    assert res.status_code == 201
    assert res.json()["expires_at"] is not None


@pytest.mark.asyncio
async def test_create_api_key_unauthorized(client: AsyncClient):
    """Token olmadan API key oluşturulamaz."""
    res = await client.post("/api/v1/api-keys", json={"name": "Unauthorized"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_create_api_key_empty_name_fails(client: AsyncClient):
    """Boş isimle API key oluşturulamaz."""
    headers = await _auth_headers(client, "apikey_emptyname@example.com")

    res = await client.post(
        "/api/v1/api-keys",
        json={"name": "   "},
        headers=headers,
    )

    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_api_key_name_too_long(client: AsyncClient):
    """100 karakterden uzun isimle API key oluşturulamaz."""
    headers = await _auth_headers(client, "apikey_longname@example.com")

    res = await client.post(
        "/api/v1/api-keys",
        json={"name": "A" * 101},
        headers=headers,
    )

    assert res.status_code == 422


# ── GET /api-keys ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_api_keys_empty(client: AsyncClient):
    """Hiç API key yokken boş liste döner."""
    headers = await _auth_headers(client, "apikey_list_empty@example.com")

    res = await client.get("/api/v1/api-keys", headers=headers)

    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_list_api_keys_shows_created_keys(client: AsyncClient):
    """Oluşturulan API key'ler listede görünmeli."""
    headers = await _auth_headers(client, "apikey_list_created@example.com")
    await _create_key(client, headers, "Key One")
    await _create_key(client, headers, "Key Two")

    res = await client.get("/api/v1/api-keys", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    names = {k["name"] for k in data}
    assert "Key One" in names
    assert "Key Two" in names


@pytest.mark.asyncio
async def test_list_api_keys_no_raw_key(client: AsyncClient):
    """Liste yanıtında ham key değeri bulunmamalı."""
    headers = await _auth_headers(client, "apikey_list_noraw@example.com")
    await _create_key(client, headers, "Secret Key")

    res = await client.get("/api/v1/api-keys", headers=headers)

    data = res.json()
    assert len(data) == 1
    assert "key" not in data[0]  # ham key listede yok
    assert "key_prefix" in data[0]


@pytest.mark.asyncio
async def test_list_api_keys_unauthorized(client: AsyncClient):
    """Token olmadan API key listesi alınamaz."""
    res = await client.get("/api/v1/api-keys")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_list_api_keys_isolated_per_user(client: AsyncClient):
    """Kullanıcı sadece kendi key'lerini görmeli."""
    headers_a = await _auth_headers(client, "apikey_user_a@example.com")
    headers_b = await _auth_headers(client, "apikey_user_b@example.com")

    await _create_key(client, headers_a, "User A Key")

    res_b = await client.get("/api/v1/api-keys", headers=headers_b)
    assert res_b.json() == []


# ── DELETE /api-keys/{id} ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_revoke_api_key_success(client: AsyncClient):
    """API key başarıyla iptal edilmeli."""
    headers = await _auth_headers(client, "apikey_revoke@example.com")
    created = await _create_key(client, headers, "Revoke Me")
    key_id = created["id"]

    res = await client.delete(f"/api/v1/api-keys/{key_id}", headers=headers)

    assert res.status_code == 200
    assert "iptal" in res.json()["message"].lower()


@pytest.mark.asyncio
async def test_revoked_key_not_in_list(client: AsyncClient):
    """İptal edilen API key listede görünmemeli."""
    headers = await _auth_headers(client, "apikey_revoke_list@example.com")
    created = await _create_key(client, headers, "Temp Key")
    key_id = created["id"]

    await client.delete(f"/api/v1/api-keys/{key_id}", headers=headers)

    res = await client.get("/api/v1/api-keys", headers=headers)
    assert res.json() == []


@pytest.mark.asyncio
async def test_revoke_nonexistent_key(client: AsyncClient):
    """Var olmayan API key iptali → 404."""
    headers = await _auth_headers(client, "apikey_revoke_404@example.com")

    res = await client.delete(f"/api/v1/api-keys/{uuid4()}", headers=headers)

    assert res.status_code == 404


@pytest.mark.asyncio
async def test_revoke_other_users_key(client: AsyncClient):
    """Başka kullanıcının API key'i iptal edilemez."""
    headers_a = await _auth_headers(client, "apikey_cross_a@example.com")
    headers_b = await _auth_headers(client, "apikey_cross_b@example.com")

    created = await _create_key(client, headers_a, "User A Key")
    key_id = created["id"]

    # B kullanıcısı A'nın key'ini silmeye çalışıyor
    res = await client.delete(f"/api/v1/api-keys/{key_id}", headers=headers_b)

    assert res.status_code == 404


@pytest.mark.asyncio
async def test_revoke_api_key_unauthorized(client: AsyncClient):
    """Token olmadan API key iptal edilemez."""
    res = await client.delete(f"/api/v1/api-keys/{uuid4()}")
    assert res.status_code == 401


# ── X-API-Key Authentication ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_key_authentication_works(client: AsyncClient):
    """X-API-Key header ile kimlik doğrulaması yapılabilmeli."""
    headers = await _auth_headers(client, "apikey_auth@example.com")
    created = await _create_key(client, headers, "Auth Key")
    raw_key = created["key"]

    # X-API-Key header ile korunan bir endpoint'e eriş
    res = await client.get(
        "/api/v1/users/me",
        headers={"X-API-Key": raw_key},
    )

    assert res.status_code == 200
    assert res.json()["email"] == "apikey_auth@example.com"


@pytest.mark.asyncio
async def test_api_key_invalid_format(client: AsyncClient):
    """Geçersiz API key formatı → 401."""
    res = await client.get(
        "/api/v1/users/me",
        headers={"X-API-Key": "invalid_key_format"},
    )

    assert res.status_code == 401


@pytest.mark.asyncio
async def test_api_key_revoked_cannot_authenticate(client: AsyncClient):
    """İptal edilen API key ile kimlik doğrulaması yapılamaz."""
    headers = await _auth_headers(client, "apikey_revoked_auth@example.com")
    created = await _create_key(client, headers, "Revoke Auth Key")
    raw_key = created["key"]
    key_id = created["id"]

    # Key'i iptal et
    await client.delete(f"/api/v1/api-keys/{key_id}", headers=headers)

    # İptal edilmiş key ile erişim denemesi
    res = await client.get(
        "/api/v1/users/me",
        headers={"X-API-Key": raw_key},
    )

    assert res.status_code == 401
