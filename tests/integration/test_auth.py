"""Auth endpoint testleri."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock

import fakeredis.aioredis as fakeredis_aioredis


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "StrongPass1",
            "full_name": "Test User",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "test@example.com"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    payload = {"email": "dup@example.com", "password": "StrongPass1"}
    await client.post("/api/v1/auth/register", json=payload)
    res = await client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "login@example.com",
            "password": "StrongPass1",
        },
    )
    res = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "login@example.com",
            "password": "StrongPass1",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    res = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "WrongPass1",
        },
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient):
    # Register + login
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "me@example.com",
            "password": "StrongPass1",
        },
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "me@example.com",
            "password": "StrongPass1",
        },
    )
    token = login.json()["access_token"]

    res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    res = await client.get("/api/v1/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


# ── Email Verification ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_email_success(
    client: AsyncClient,
    fake_redis: fakeredis_aioredis.FakeRedis,
    mock_enqueue: AsyncMock,
):
    """Kayıt sonrası oluşturulan token ile e-posta doğrulaması başarılı olmalı."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "verify@example.com",
            "password": "StrongPass1",
        },
    )
    # enqueue(send_verification_email, email, token) çağrısından token'ı al
    token = mock_enqueue.call_args.args[2]

    res = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert res.status_code == 200
    assert "doğrulandı" in res.json()["message"]

    # Token tek kullanımlık — Redis'ten silinmiş olmalı
    assert await fake_redis.get(f"email_verify:{token}") is None


@pytest.mark.asyncio
async def test_verify_email_invalid_token(client: AsyncClient):
    """Geçersiz token 401 döndürmeli."""
    res = await client.post("/api/v1/auth/verify-email", json={"token": "invalid-token-xyz"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_resend_verification(client: AsyncClient, mock_enqueue: AsyncMock):
    """Doğrulanmamış kullanıcı için yeniden e-posta gönderilmeli."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "resend@example.com",
            "password": "StrongPass1",
        },
    )
    mock_enqueue.reset_mock()

    res = await client.post(
        "/api/v1/auth/resend-verification", json={"email": "resend@example.com"}
    )
    assert res.status_code == 200
    mock_enqueue.assert_called_once()


@pytest.mark.asyncio
async def test_resend_verification_nonexistent_email(client: AsyncClient, mock_enqueue: AsyncMock):
    """Var olmayan e-posta için 200 dönmeli, e-posta gönderilmemeli (user enumeration yok)."""
    mock_enqueue.reset_mock()
    res = await client.post("/api/v1/auth/resend-verification", json={"email": "ghost@example.com"})
    assert res.status_code == 200
    mock_enqueue.assert_not_called()


# ── Password Reset ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_forgot_password_returns_200_always(client: AsyncClient, mock_enqueue: AsyncMock):
    """Var olmayan kullanıcı için de 200 dönmeli (user enumeration yok)."""
    mock_enqueue.reset_mock()
    res = await client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert res.status_code == 200
    mock_enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_forgot_password_existing_user(client: AsyncClient, mock_enqueue: AsyncMock):
    """Var olan kullanıcı için e-posta gönderme task'ı enqueue edilmeli."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "reset@example.com",
            "password": "StrongPass1",
        },
    )
    mock_enqueue.reset_mock()

    res = await client.post("/api/v1/auth/forgot-password", json={"email": "reset@example.com"})
    assert res.status_code == 200
    mock_enqueue.assert_called_once()


@pytest.mark.asyncio
async def test_reset_password_success(
    client: AsyncClient,
    fake_redis: fakeredis_aioredis.FakeRedis,
    mock_enqueue: AsyncMock,
):
    """Token ile şifre sıfırlandıktan sonra yeni şifre ile giriş yapılabilmeli."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "pwreset@example.com",
            "password": "StrongPass1",
        },
    )
    mock_enqueue.reset_mock()

    await client.post("/api/v1/auth/forgot-password", json={"email": "pwreset@example.com"})
    token = mock_enqueue.call_args.args[2]

    res = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": token,
            "new_password": "NewStrongPass2",
        },
    )
    assert res.status_code == 200

    # Token tüketildi — Redis'ten silinmiş olmalı
    assert await fake_redis.get(f"password_reset:{token}") is None

    # Yeni şifre ile giriş yapılabilmeli
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "pwreset@example.com",
            "password": "NewStrongPass2",
        },
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_invalid_token(client: AsyncClient):
    """Geçersiz token 401 döndürmeli."""
    res = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": "bad-token-xyz",
            "new_password": "NewStrongPass2",
        },
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_reset_password_token_one_time_use(
    client: AsyncClient,
    mock_enqueue: AsyncMock,
):
    """Aynı token ikinci kez kullanılamamalı."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "oneuse@example.com",
            "password": "StrongPass1",
        },
    )
    mock_enqueue.reset_mock()

    await client.post("/api/v1/auth/forgot-password", json={"email": "oneuse@example.com"})
    token = mock_enqueue.call_args.args[2]

    await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": token,
            "new_password": "NewStrongPass2",
        },
    )

    # İkinci kullanım başarısız olmalı
    res = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": token,
            "new_password": "AnotherPass3",
        },
    )
    assert res.status_code == 401


# ── Token Blacklist + Refresh Rotation ────────────────────────────────────────


async def _register_and_login(client: AsyncClient, email: str) -> dict:
    """Yardımcı: kayıt + giriş → token çifti döner."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "StrongPass1",
        },
    )
    res = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "StrongPass1",
        },
    )
    return res.json()


@pytest.mark.asyncio
async def test_logout_invalidates_access_token(client: AsyncClient):
    """Logout sonrası aynı access token ile /me çağrısı 401 dönmeli."""
    tokens = await _register_and_login(client, "logout_access@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=headers,
    )

    res = await client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_logout_invalidates_refresh_token(client: AsyncClient):
    """Logout sonrası aynı refresh token ile /refresh çağrısı 401 dönmeli."""
    tokens = await _register_and_login(client, "logout_refresh@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=headers,
    )

    res = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_rotation(client: AsyncClient):
    """Refresh sonrası eski refresh token geçersiz kılınmalı (rotation)."""
    tokens = await _register_and_login(client, "rotation@example.com")
    old_refresh = tokens["refresh_token"]

    # İlk refresh — yeni token çifti alınır
    res = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert res.status_code == 200

    # Eski refresh token artık kullanılamamalı
    res = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_refresh_blacklisted_token(client: AsyncClient):
    """Logout ile blacklist'e alınan refresh token /refresh'te 401 dönmeli."""
    tokens = await _register_and_login(client, "blacklist_refresh@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=headers,
    )

    res = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert res.status_code == 401
