"""
E2E test: 2FA kurulum ve kullanım yolculuğu.

Kayıt → giriş → TOTP kurulum → TOTP etkinleştirme → çıkış → TOTP ile giriş
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pyotp
import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


@pytest.mark.asyncio
async def test_full_2fa_journey(client: AsyncClient) -> None:
    """
    Adım 1: Kayıt → 201
    Adım 2: Giriş (TOTP yok) → 200
    Adım 3: TOTP kurulum → 200, secret + QR kodu alınır
    Adım 4: Geçerli kodla TOTP etkinleştir → 200, 8 backup kodu alınır
    Adım 5: Çıkış → 200
    Adım 6: TOTP kodu olmadan giriş → 401
    Adım 7: Geçerli TOTP kodu ile giriş → 200
    Adım 8: Hatalı TOTP kodu ile giriş → 401
    """
    email = "journey_2fa@example.com"
    password = "StrongPass1"

    # Adım 1: Kayıt
    reg = await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert reg.status_code == 201

    # Adım 2: Giriş (2FA yok)
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    access_token = login.json()["access_token"]
    refresh_token = login.json()["refresh_token"]
    auth_headers = {"Authorization": f"Bearer {access_token}"}

    # Adım 3: TOTP kurulum
    setup = await client.post("/api/v1/auth/totp/setup", headers=auth_headers)
    assert setup.status_code == 200
    data = setup.json()
    assert "secret" in data
    assert "qr_code" in data
    assert "provisioning_uri" in data
    assert data["qr_code"].startswith("data:image/png;base64,")
    secret = data["secret"]

    # Adım 4: TOTP etkinleştir
    valid_code = pyotp.TOTP(secret).now()
    verify = await client.post(
        "/api/v1/auth/totp/verify", json={"code": valid_code}, headers=auth_headers
    )
    assert verify.status_code == 200
    backup_codes = verify.json()["backup_codes"]
    assert len(backup_codes) == 8

    # Adım 5: Çıkış
    logout = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers=auth_headers,
    )
    assert logout.status_code == 200

    # Adım 6: TOTP kodu olmadan giriş → partial_token challenge (200)
    no_code = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert no_code.status_code == 200
    assert no_code.json()["requires_totp"] is True
    partial = no_code.json()["partial_token"]

    # Adım 7: partial_token + geçerli TOTP kodu ile challenge → 200
    totp_login = await client.post(
        "/api/v1/auth/totp-challenge",
        json={"partial_token": partial, "code": pyotp.TOTP(secret).now()},
    )
    assert totp_login.status_code == 200
    assert "access_token" in totp_login.json()
    new_auth_headers = {"Authorization": f"Bearer {totp_login.json()['access_token']}"}

    # Adım 8: Hatalı TOTP kodu ile challenge → 401 (yeni partial_token al)
    step8_partial = (
        await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    ).json()["partial_token"]
    bad_login = await client.post(
        "/api/v1/auth/totp-challenge",
        json={"partial_token": step8_partial, "code": "000000"},
    )
    assert bad_login.status_code == 401

    # Bonus: TOTP'yi devre dışı bırak (temizlik)
    disable_code = pyotp.TOTP(secret).now()
    disable = await client.post(
        "/api/v1/auth/totp/disable",
        json={"code": disable_code},
        headers=new_auth_headers,
    )
    assert disable.status_code == 200

    # TOTP devre dışıyken kod olmadan giriş → 200
    plain_login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert plain_login.status_code == 200
