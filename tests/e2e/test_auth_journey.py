"""
E2E test: Tam kimlik doğrulama yolculuğu.

Kayıt → e-posta doğrulama → giriş → profil → token yenileme → çıkış → blacklist kontrolü
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from unittest.mock import AsyncMock

    import fakeredis.aioredis as fakeredis_aioredis
    from httpx import AsyncClient


@pytest.mark.asyncio
async def test_full_auth_journey(
    client: AsyncClient,
    fake_redis: fakeredis_aioredis.FakeRedis,
    mock_enqueue: AsyncMock,
) -> None:
    """
    Adım 1: Kayıt → 201, kullanıcı oluşturulur
    Adım 2: E-posta doğrulama (enqueue çağrısından token al) → 200
    Adım 3: Giriş → 200, access + refresh token alınır
    Adım 4: GET /users/me ile profil → 200, email eşleşmeli
    Adım 5: POST /auth/refresh ile token yenile → 200, yeni tokenlar
    Adım 6: Yeni access token ile /users/me → 200
    Adım 7: Çıkış (logout) → 200
    Adım 8: Çıkış sonrası access token → 401 (blacklisted)
    Adım 9: Çıkış sonrası refresh token → 401 (blacklisted)
    """
    email = "journey_auth@example.com"
    password = "StrongPass1"

    # Adım 1: Kayıt
    reg = await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert reg.status_code == 201
    assert reg.json()["email"] == email

    # Adım 2: E-posta doğrulama
    token = mock_enqueue.call_args.args[2]
    verify = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert verify.status_code == 200
    assert await fake_redis.get(f"email_verify:{token}") is None  # token tüketildi

    # Adım 3: Giriş
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    tokens = login.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]
    auth_headers = {"Authorization": f"Bearer {access_token}"}

    # Adım 4: Profil
    me = await client.get("/api/v1/users/me", headers=auth_headers)
    assert me.status_code == 200
    assert me.json()["email"] == email
    assert me.json()["is_verified"] is True

    # Adım 5: Token yenileme
    refresh = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh.status_code == 200
    new_tokens = refresh.json()
    new_access = new_tokens["access_token"]
    new_refresh = new_tokens["refresh_token"]
    new_headers = {"Authorization": f"Bearer {new_access}"}

    # Eski refresh token artık geçersiz (rotation)
    old_refresh_res = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert old_refresh_res.status_code == 401

    # Adım 6: Yeni access token çalışıyor
    me2 = await client.get("/api/v1/users/me", headers=new_headers)
    assert me2.status_code == 200

    # Adım 7: Çıkış
    logout = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": new_refresh},
        headers=new_headers,
    )
    assert logout.status_code == 200

    # Adım 8: Access token blacklist'te
    me3 = await client.get("/api/v1/users/me", headers=new_headers)
    assert me3.status_code == 401

    # Adım 9: Refresh token blacklist'te
    re_refresh = await client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert re_refresh.status_code == 401
