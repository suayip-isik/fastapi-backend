"""Users endpoint testleri — /api/v1/users/"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import update as sa_update

from app.db.models.user import User, UserRole

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _register_and_login(
    client: AsyncClient,
    email: str,
    password: str = "StrongPass1",
) -> dict:
    """Yardımcı fonksiyon."""
    await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return res.json()


async def _auth_headers(client: AsyncClient, email: str, password: str = "StrongPass1") -> dict:
    """Yardımcı fonksiyon."""
    tokens = await _register_and_login(client, email, password)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _promote_to_admin(db_session: AsyncSession, email: str) -> None:
    """Kullanıcıyı ADMIN rolüne yükselt (commit gereksiz — aynı transaction içinde görünür)."""
    await db_session.execute(sa_update(User).where(User.email == email).values(role=UserRole.ADMIN))
    db_session.expire_all()


# ── GET /users/me ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_users_me(client: AsyncClient):
    """test_get_users_me senaryosunu test eder."""
    headers = await _auth_headers(client, "users_me@example.com")
    res = await client.get("/api/v1/users/me", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "users_me@example.com"
    assert "id" in data
    assert data["is_active"] is True
    assert data["role"] == "user"


@pytest.mark.asyncio
async def test_get_users_me_unauthorized(client: AsyncClient):
    """test_get_users_me_unauthorized senaryosunu test eder."""
    res = await client.get("/api/v1/users/me")
    assert res.status_code == 401


# ── PATCH /users/me ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_me_full_name(client: AsyncClient):
    """test_update_me_full_name senaryosunu test eder."""
    headers = await _auth_headers(client, "update_name@example.com")
    res = await client.patch(
        "/api/v1/users/me", json={"full_name": "Yeni Ad Soyad"}, headers=headers
    )

    assert res.status_code == 200
    assert res.json()["full_name"] == "Yeni Ad Soyad"


@pytest.mark.asyncio
async def test_update_me_username(client: AsyncClient):
    """test_update_me_username senaryosunu test eder."""
    headers = await _auth_headers(client, "update_username@example.com")
    res = await client.patch(
        "/api/v1/users/me", json={"username": "yeni_kullanici"}, headers=headers
    )

    assert res.status_code == 200
    assert res.json()["username"] == "yeni_kullanici"


@pytest.mark.asyncio
async def test_update_me_email(client: AsyncClient):
    """test_update_me_email senaryosunu test eder."""
    headers = await _auth_headers(client, "old_email@example.com")
    res = await client.patch(
        "/api/v1/users/me", json={"email": "new_address@example.com"}, headers=headers
    )

    assert res.status_code == 200
    assert res.json()["email"] == "new_address@example.com"


@pytest.mark.asyncio
async def test_update_me_email_duplicate(client: AsyncClient):
    """test_update_me_email_duplicate senaryosunu test eder."""
    await _auth_headers(client, "taken@example.com")
    headers = await _auth_headers(client, "wants_taken@example.com")

    res = await client.patch(
        "/api/v1/users/me", json={"email": "taken@example.com"}, headers=headers
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_update_me_password(client: AsyncClient):
    """test_update_me_password senaryosunu test eder."""
    email = "change_pw@example.com"
    headers = await _auth_headers(client, email)

    res = await client.patch("/api/v1/users/me", json={"password": "NewPass123"}, headers=headers)
    assert res.status_code == 200

    # Yeni şifre çalışmalı
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "NewPass123"})
    assert login.status_code == 200

    # Eski şifre artık çalışmamalı
    old_login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "StrongPass1"}
    )
    assert old_login.status_code == 401


@pytest.mark.asyncio
async def test_update_me_unauthorized(client: AsyncClient):
    """test_update_me_unauthorized senaryosunu test eder."""
    res = await client.patch("/api/v1/users/me", json={"full_name": "Foo"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_update_me_no_fields_returns_current_user(client: AsyncClient):
    """Hiçbir alan gönderilmezse mevcut kullanıcı döner — 200."""
    headers = await _auth_headers(client, "noop_update@example.com")
    res = await client.patch("/api/v1/users/me", json={}, headers=headers)

    assert res.status_code == 200
    assert res.json()["email"] == "noop_update@example.com"


# ── GET /users (Admin only) ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_users_as_admin(client: AsyncClient, db_session: AsyncSession):
    """test_list_users_as_admin senaryosunu test eder."""
    email = "admin_list@example.com"
    headers = await _auth_headers(client, email)
    await _promote_to_admin(db_session, email)

    res = await client.get("/api/v1/users", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "pages" in data
    assert isinstance(data["items"], list)
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_list_users_as_non_admin(client: AsyncClient):
    """test_list_users_as_non_admin senaryosunu test eder."""
    headers = await _auth_headers(client, "non_admin_list@example.com")
    res = await client.get("/api/v1/users", headers=headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_list_users_unauthorized(client: AsyncClient):
    """test_list_users_unauthorized senaryosunu test eder."""
    res = await client.get("/api/v1/users")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_list_users_pagination(client: AsyncClient, db_session: AsyncSession):
    """test_list_users_pagination senaryosunu test eder."""
    admin_email = "admin_pager@example.com"
    await _auth_headers(client, "pager_u1@example.com")
    await _auth_headers(client, "pager_u2@example.com")
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.get("/api/v1/users?page=1&size=2", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) <= 2
    assert data["size"] == 2
    assert data["page"] == 1
    assert data["pages"] >= 1


@pytest.mark.asyncio
async def test_list_users_default_pagination(client: AsyncClient, db_session: AsyncSession):
    """test_list_users_default_pagination senaryosunu test eder."""
    admin_email = "admin_defpager@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.get("/api/v1/users", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["page"] == 1
    assert data["size"] == 20


# ── GET /users/{id} (Admin only) ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_user_by_id_as_admin(client: AsyncClient, db_session: AsyncSession):
    """test_get_user_by_id_as_admin senaryosunu test eder."""
    admin_email = "admin_getid@example.com"
    target_email = "target_getid@example.com"

    # Hedef kullanıcının ID'sini al
    target_headers = await _auth_headers(client, target_email)
    target_me = await client.get("/api/v1/users/me", headers=target_headers)
    target_id = target_me.json()["id"]

    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.get(f"/api/v1/users/{target_id}", headers=headers)

    assert res.status_code == 200
    assert res.json()["email"] == target_email


@pytest.mark.asyncio
async def test_get_user_by_id_as_non_admin(client: AsyncClient):
    """test_get_user_by_id_as_non_admin senaryosunu test eder."""
    target_headers = await _auth_headers(client, "target_perm@example.com")
    target_me = await client.get("/api/v1/users/me", headers=target_headers)
    target_id = target_me.json()["id"]

    non_admin_headers = await _auth_headers(client, "non_admin_perm@example.com")
    res = await client.get(f"/api/v1/users/{target_id}", headers=non_admin_headers)

    assert res.status_code == 403


@pytest.mark.asyncio
async def test_get_user_by_id_unauthorized(client: AsyncClient):
    """test_get_user_by_id_unauthorized senaryosunu test eder."""
    res = await client.get("/api/v1/users/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_user_by_id_not_found(client: AsyncClient, db_session: AsyncSession):
    """test_get_user_by_id_not_found senaryosunu test eder."""
    admin_email = "admin_notfound@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    fake_id = "00000000-0000-0000-0000-000000000000"
    res = await client.get(f"/api/v1/users/{fake_id}", headers=headers)

    assert res.status_code == 404


# ── DELETE /users/{id} (Admin only) ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_deactivate_user_as_admin(client: AsyncClient, db_session: AsyncSession):
    """test_deactivate_user_as_admin senaryosunu test eder."""
    admin_email = "admin_deact@example.com"
    target_email = "target_deact@example.com"

    target_headers = await _auth_headers(client, target_email)
    target_me = await client.get("/api/v1/users/me", headers=target_headers)
    target_id = target_me.json()["id"]

    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.delete(f"/api/v1/users/{target_id}", headers=headers)
    assert res.status_code == 200
    assert "silindi" in res.json()["message"]

    # Soft-deleted kullanıcı artık giriş yapamamalı
    login = await client.post(
        "/api/v1/auth/login", json={"email": target_email, "password": "StrongPass1"}
    )
    assert login.status_code == 401


@pytest.mark.asyncio
async def test_deactivate_user_as_non_admin(client: AsyncClient):
    """test_deactivate_user_as_non_admin senaryosunu test eder."""
    target_headers = await _auth_headers(client, "target_nodeact@example.com")
    target_me = await client.get("/api/v1/users/me", headers=target_headers)
    target_id = target_me.json()["id"]

    non_admin_headers = await _auth_headers(client, "non_admin_nodeact@example.com")
    res = await client.delete(f"/api/v1/users/{target_id}", headers=non_admin_headers)

    assert res.status_code == 403


@pytest.mark.asyncio
async def test_deactivate_user_unauthorized(client: AsyncClient):
    """test_deactivate_user_unauthorized senaryosunu test eder."""
    res = await client.delete("/api/v1/users/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_deactivate_nonexistent_user(client: AsyncClient, db_session: AsyncSession):
    """Admin ile var olmayan UUID → 404."""
    admin_email = "admin_404del@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    fake_id = "00000000-0000-0000-0000-000000000001"
    res = await client.delete(f"/api/v1/users/{fake_id}", headers=headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_update_me_password_too_short(client: AsyncClient):
    """8 karakterden kısa şifre ile PATCH /users/me → 422."""
    headers = await _auth_headers(client, "shortpw_update@example.com")
    res = await client.patch("/api/v1/users/me", json={"password": "Sh0rt"}, headers=headers)
    assert res.status_code == 422
