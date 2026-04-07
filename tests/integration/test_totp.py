"""TOTP / 2FA endpoint testleri — /api/v1/auth/totp"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pyotp
import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

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


async def _setup_and_enable_totp(client: AsyncClient, headers: dict) -> str:
    """TOTP'yi setup eder, doğrular ve etkinleştirir. Secret döner."""
    setup_res = await client.post("/api/v1/auth/totp/setup", headers=headers)
    secret = setup_res.json()["secret"]
    code = pyotp.TOTP(secret).now()
    await client.post("/api/v1/auth/totp/verify", json={"code": code}, headers=headers)
    return secret


# ── POST /auth/totp/setup ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_totp_setup_returns_secret_and_qr(client: AsyncClient):
    """Setup QR kod, secret ve provisioning URI döndürmeli."""
    headers = await _auth_headers(client, "totp_setup@example.com")

    res = await client.post("/api/v1/auth/totp/setup", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert "secret" in data
    assert "qr_code" in data
    assert data["qr_code"].startswith("data:image/png;base64,")
    assert "provisioning_uri" in data
    assert "message" in data


@pytest.mark.asyncio
async def test_totp_setup_unauthorized(client: AsyncClient):
    """Token olmadan TOTP setup yapılamaz."""
    res = await client.post("/api/v1/auth/totp/setup")
    assert res.status_code == 401


# ── POST /auth/totp/verify ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_totp_verify_enables_2fa(client: AsyncClient):
    """Geçerli TOTP kodu ile 2FA aktif edilebilmeli."""
    headers = await _auth_headers(client, "totp_verify@example.com")

    setup_res = await client.post("/api/v1/auth/totp/setup", headers=headers)
    secret = setup_res.json()["secret"]
    code = pyotp.TOTP(secret).now()

    res = await client.post("/api/v1/auth/totp/verify", json={"code": code}, headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert "backup_codes" in data
    assert len(data["backup_codes"]) == 8


@pytest.mark.asyncio
async def test_totp_verify_invalid_code_fails(client: AsyncClient):
    """Geçersiz TOTP kodu ile doğrulama başarısız olmalı."""
    headers = await _auth_headers(client, "totp_verify_invalid@example.com")
    await client.post("/api/v1/auth/totp/setup", headers=headers)

    res = await client.post("/api/v1/auth/totp/verify", json={"code": "000000"}, headers=headers)

    assert res.status_code == 401  # AuthenticationError → 401


@pytest.mark.asyncio
async def test_totp_verify_without_setup_fails(client: AsyncClient):
    """Setup yapmadan doğrulama denemesi başarısız olmalı."""
    headers = await _auth_headers(client, "totp_verify_no_setup@example.com")

    res = await client.post("/api/v1/auth/totp/verify", json={"code": "123456"}, headers=headers)

    assert res.status_code == 400


@pytest.mark.asyncio
async def test_totp_verify_invalid_format(client: AsyncClient):
    """6 haneli olmayan TOTP kodu → 422."""
    headers = await _auth_headers(client, "totp_verify_format@example.com")

    res = await client.post("/api/v1/auth/totp/verify", json={"code": "abc"}, headers=headers)

    assert res.status_code == 422


# ── POST /auth/totp/disable ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_totp_disable_with_valid_code(client: AsyncClient):
    """Geçerli TOTP kodu ile 2FA devre dışı bırakılabilmeli."""
    headers = await _auth_headers(client, "totp_disable@example.com")
    secret = await _setup_and_enable_totp(client, headers)
    code = pyotp.TOTP(secret).now()

    res = await client.post("/api/v1/auth/totp/disable", json={"code": code}, headers=headers)

    assert res.status_code == 200


@pytest.mark.asyncio
async def test_totp_disable_invalid_code_fails(client: AsyncClient):
    """Geçersiz TOTP kodu ile devre dışı bırakma başarısız olmalı."""
    headers = await _auth_headers(client, "totp_disable_invalid@example.com")
    await _setup_and_enable_totp(client, headers)

    res = await client.post("/api/v1/auth/totp/disable", json={"code": "000000"}, headers=headers)

    assert res.status_code == 401  # AuthenticationError → 401


@pytest.mark.asyncio
async def test_totp_disable_when_not_enabled_fails(client: AsyncClient):
    """2FA aktif değilken disable denemesi başarısız olmalı."""
    headers = await _auth_headers(client, "totp_disable_inactive@example.com")

    res = await client.post("/api/v1/auth/totp/disable", json={"code": "123456"}, headers=headers)

    assert res.status_code == 400


# ── GET /auth/totp/backup-codes/count ────────────────────────────────────────


@pytest.mark.asyncio
async def test_backup_code_count_after_enable(client: AsyncClient):
    """2FA aktif ettikten sonra backup kod sayısı 8 olmalı."""
    headers = await _auth_headers(client, "totp_backup_count@example.com")
    await _setup_and_enable_totp(client, headers)

    res = await client.get("/api/v1/auth/totp/backup-codes/count", headers=headers)

    assert res.status_code == 200
    assert res.json()["count"] == 8


@pytest.mark.asyncio
async def test_backup_code_count_without_totp_fails(client: AsyncClient):
    """2FA aktif değilken backup kod sayısı → 400."""
    headers = await _auth_headers(client, "totp_count_no_totp@example.com")

    res = await client.get("/api/v1/auth/totp/backup-codes/count", headers=headers)

    assert res.status_code == 400


# ── POST /auth/totp/backup-codes/regenerate ───────────────────────────────────


@pytest.mark.asyncio
async def test_regenerate_backup_codes(client: AsyncClient):
    """Geçerli TOTP kodu ile backup kodlar yenilenebilmeli."""
    headers = await _auth_headers(client, "totp_regen@example.com")
    secret = await _setup_and_enable_totp(client, headers)
    code = pyotp.TOTP(secret).now()

    res = await client.post(
        "/api/v1/auth/totp/backup-codes/regenerate",
        json={"code": code},
        headers=headers,
    )

    assert res.status_code == 200
    data = res.json()
    assert "backup_codes" in data
    assert len(data["backup_codes"]) == 8


@pytest.mark.asyncio
async def test_regenerate_backup_codes_invalid_totp_fails(client: AsyncClient):
    """Geçersiz TOTP ile backup kod yenileme başarısız olmalı."""
    headers = await _auth_headers(client, "totp_regen_invalid@example.com")
    await _setup_and_enable_totp(client, headers)

    res = await client.post(
        "/api/v1/auth/totp/backup-codes/regenerate",
        json={"code": "000000"},
        headers=headers,
    )

    assert res.status_code == 401  # AuthenticationError → 401


@pytest.mark.asyncio
async def test_regenerate_when_totp_not_active_fails(client: AsyncClient):
    """2FA aktif değilken backup kod yenileme → 400."""
    headers = await _auth_headers(client, "totp_regen_inactive@example.com")

    res = await client.post(
        "/api/v1/auth/totp/backup-codes/regenerate",
        json={"code": "123456"},
        headers=headers,
    )

    assert res.status_code == 400


# ── Backup kod ile login ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_with_backup_code(client: AsyncClient):
    """Backup kod ile TOTP challenge tamamlanabilmeli."""
    email = "totp_backup_login@example.com"
    password = "StrongPass1"
    tokens = await _register_and_login(client, email, password)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # TOTP aktif et ve backup kodları al
    setup_res = await client.post("/api/v1/auth/totp/setup", headers=headers)
    secret = setup_res.json()["secret"]
    code = pyotp.TOTP(secret).now()
    verify_res = await client.post("/api/v1/auth/totp/verify", json={"code": code}, headers=headers)
    backup_codes = verify_res.json()["backup_codes"]

    # Login ile partial_token al
    step1 = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert step1.status_code == 200
    partial_token = step1.json()["partial_token"]

    # Backup kod ile challenge tamamla
    step2 = await client.post(
        "/api/v1/auth/totp-challenge",
        json={"partial_token": partial_token, "code": backup_codes[0]},
    )

    assert step2.status_code == 200
    assert "access_token" in step2.json()


@pytest.mark.asyncio
async def test_backup_code_single_use(client: AsyncClient):
    """Backup kod ikinci kez kullanılamaz."""
    email = "totp_backup_single@example.com"
    password = "StrongPass1"
    tokens = await _register_and_login(client, email, password)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    setup_res = await client.post("/api/v1/auth/totp/setup", headers=headers)
    secret = setup_res.json()["secret"]
    code = pyotp.TOTP(secret).now()
    verify_res = await client.post("/api/v1/auth/totp/verify", json={"code": code}, headers=headers)
    backup_codes = verify_res.json()["backup_codes"]

    # İlk kullanım
    step1 = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    partial_token = step1.json()["partial_token"]
    step2 = await client.post(
        "/api/v1/auth/totp-challenge",
        json={"partial_token": partial_token, "code": backup_codes[0]},
    )
    assert step2.status_code == 200

    # İkinci kullanım — aynı kod tekrar kullanılmaya çalışılıyor
    step3 = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    partial_token2 = step3.json()["partial_token"]
    step4 = await client.post(
        "/api/v1/auth/totp-challenge",
        json={"partial_token": partial_token2, "code": backup_codes[0]},
    )
    assert step4.status_code == 401
