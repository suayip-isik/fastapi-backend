"""
E2E test: API key yaşam döngüsü yolculuğu.

Kayıt → key oluşturma → key ile erişim → ikinci key → iptal → iptal edilmiş key reddi
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


@pytest.mark.asyncio
async def test_full_api_key_journey(client: AsyncClient) -> None:
    """
    Adım 1: Kayıt → 201
    Adım 2: Giriş → 200, JWT token alınır
    Adım 3: JWT ile API key oluştur → 201, ham key (sk_live_*) alınır
    Adım 4: X-API-Key header ile /users/me → 200, email eşleşmeli
    Adım 5: API key listesi → 200, 1 aktif key
    Adım 6: İkinci API key oluştur → 201
    Adım 7: API key listesi → 200, 2 aktif key
    Adım 8: Birinci key'i iptal et → 200
    Adım 9: İptal edilmiş key → 401
    Adım 10: İkinci key hâlâ çalışıyor → 200
    Adım 11: Kalan API key listesi → 200, 1 aktif key
    """
    email = "journey_apikey@example.com"
    password = "StrongPass1"

    # Adım 1+2: Kayıt ve giriş
    await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    jwt_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Adım 3: İlk API key oluştur
    create1 = await client.post(
        "/api/v1/api-keys", json={"name": "Journey Key 1"}, headers=jwt_headers
    )
    assert create1.status_code == 201
    raw_key_1 = create1.json()["key"]
    key_id_1 = create1.json()["id"]
    assert raw_key_1.startswith("sk_live_")
    assert len(raw_key_1) == 88  # "sk_live_" (8) + token_hex(40) (80)

    # Adım 4: API key ile erişim
    me = await client.get("/api/v1/users/me", headers={"X-API-Key": raw_key_1})
    assert me.status_code == 200
    assert me.json()["email"] == email

    # Adım 5: Liste → 1 key
    keys = await client.get("/api/v1/api-keys", headers=jwt_headers)
    assert keys.status_code == 200
    assert len(keys.json()) == 1
    assert keys.json()[0]["name"] == "Journey Key 1"

    # Adım 6: İkinci API key
    create2 = await client.post(
        "/api/v1/api-keys", json={"name": "Journey Key 2"}, headers=jwt_headers
    )
    assert create2.status_code == 201
    raw_key_2 = create2.json()["key"]

    # Adım 7: Liste → 2 key
    keys2 = await client.get("/api/v1/api-keys", headers=jwt_headers)
    assert len(keys2.json()) == 2

    # Adım 8: Birinci key'i iptal et
    revoke = await client.delete(f"/api/v1/api-keys/{key_id_1}", headers=jwt_headers)
    assert revoke.status_code == 200

    # Adım 9: İptal edilmiş key reddedilmeli
    rejected = await client.get("/api/v1/users/me", headers={"X-API-Key": raw_key_1})
    assert rejected.status_code == 401

    # Adım 10: İkinci key hâlâ geçerli
    still_works = await client.get("/api/v1/users/me", headers={"X-API-Key": raw_key_2})
    assert still_works.status_code == 200
    assert still_works.json()["email"] == email

    # Adım 11: Kalan key listesi → 1 key (sadece ikinci)
    remaining = await client.get("/api/v1/api-keys", headers=jwt_headers)
    assert len(remaining.json()) == 1
    assert remaining.json()[0]["name"] == "Journey Key 2"
