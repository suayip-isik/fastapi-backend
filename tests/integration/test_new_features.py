"""
TOTP, API Key ve Notification modülleri için integration testleri.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _register_and_login(
    client: AsyncClient, email: str, password: str = "StrongPass1"
) -> dict[str, str]:
    """Yardımcı fonksiyon."""
    await client.post("/api/v1/client/auth/register", json={"email": email, "password": password})
    res = await client.post(
        "/api/v1/client/auth/login", json={"email": email, "password": password}
    )
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


# ═══════════════════════════════════════════════════════════════════════════════
# TOTP / 2FA
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_totp_setup_requires_auth(client: AsyncClient) -> None:
    """test_totp_setup_requires_auth senaryosunu test eder."""
    res = await client.post("/api/v1/shared/auth/totp/setup")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_totp_setup_returns_qr_and_secret(client: AsyncClient) -> None:
    """test_totp_setup_returns_qr_and_secret senaryosunu test eder."""
    headers = await _register_and_login(client, "totp_setup@example.com")
    res = await client.post("/api/v1/shared/auth/totp/setup", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "secret" in data
    assert "qr_code" in data
    assert data["qr_code"].startswith("data:image/png;base64,")
    assert "provisioning_uri" in data


@pytest.mark.asyncio
async def test_totp_verify_invalid_code(client: AsyncClient) -> None:
    """test_totp_verify_invalid_code senaryosunu test eder."""
    headers = await _register_and_login(client, "totp_verify_bad@example.com")
    await client.post("/api/v1/shared/auth/totp/setup", headers=headers)
    res = await client.post(
        "/api/v1/shared/auth/totp/verify", json={"code": "000000"}, headers=headers
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_totp_verify_and_disable_flow(client: AsyncClient) -> None:
    """Setup → verify (mock valid code) → disable."""
    import pyotp

    headers = await _register_and_login(client, "totp_full@example.com")

    # Setup
    setup_res = await client.post("/api/v1/shared/auth/totp/setup", headers=headers)
    assert setup_res.status_code == 200
    secret = setup_res.json()["secret"]

    # Verify with valid TOTP code
    valid_code = pyotp.TOTP(secret).now()
    verify_res = await client.post(
        "/api/v1/shared/auth/totp/verify", json={"code": valid_code}, headers=headers
    )
    assert verify_res.status_code == 200
    data = verify_res.json()
    assert "backup_codes" in data
    assert len(data["backup_codes"]) == 8

    # Disable with valid code (use fresh code in case time window passed)
    valid_code2 = pyotp.TOTP(secret).now()
    disable_res = await client.post(
        "/api/v1/shared/auth/totp/disable", json={"code": valid_code2}, headers=headers
    )
    assert disable_res.status_code == 200


@pytest.mark.asyncio
async def test_totp_disable_when_not_enabled(client: AsyncClient) -> None:
    """test_totp_disable_when_not_enabled senaryosunu test eder."""
    headers = await _register_and_login(client, "totp_disable_na@example.com")
    res = await client.post(
        "/api/v1/shared/auth/totp/disable", json={"code": "123456"}, headers=headers
    )
    assert res.status_code == 400  # BusinessRuleError


@pytest.mark.asyncio
async def test_login_requires_totp_when_enabled(client: AsyncClient) -> None:
    """2FA aktif kullanıcı TOTP kodu vermeden login yapamamalı."""
    import pyotp

    email = "totp_login@example.com"
    password = "StrongPass1"
    headers = await _register_and_login(client, email, password)

    # 2FA aktif et
    setup_res = await client.post("/api/v1/shared/auth/totp/setup", headers=headers)
    secret = setup_res.json()["secret"]
    valid_code = pyotp.TOTP(secret).now()
    await client.post("/api/v1/shared/auth/totp/verify", json={"code": valid_code}, headers=headers)

    # TOTP kodu olmadan login → partial_token challenge (200)
    res = await client.post(
        "/api/v1/client/auth/login", json={"email": email, "password": password}
    )
    assert res.status_code == 200
    assert res.json()["requires_totp"] is True
    partial = res.json()["partial_token"]

    # partial_token + geçerli TOTP kodu ile challenge → 200
    res2 = await client.post(
        "/api/v1/shared/auth/totp-challenge",
        json={"partial_token": partial, "code": pyotp.TOTP(secret).now()},
    )
    assert res2.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# API Keys
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_api_key(client: AsyncClient) -> None:
    """test_create_api_key senaryosunu test eder."""
    headers = await _register_and_login(client, "apikey_create@example.com")
    res = await client.post(
        "/api/v1/shared/api-keys",
        json={"name": "My Test Key"},
        headers=headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["key"].startswith("sk_live_")
    assert data["name"] == "My Test Key"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_api_keys(client: AsyncClient) -> None:
    """test_list_api_keys senaryosunu test eder."""
    headers = await _register_and_login(client, "apikey_list@example.com")
    await client.post("/api/v1/shared/api-keys", json={"name": "Key 1"}, headers=headers)
    await client.post("/api/v1/shared/api-keys", json={"name": "Key 2"}, headers=headers)

    res = await client.get("/api/v1/shared/api-keys", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) == 2


@pytest.mark.asyncio
async def test_revoke_api_key(client: AsyncClient) -> None:
    """test_revoke_api_key senaryosunu test eder."""
    headers = await _register_and_login(client, "apikey_revoke@example.com")
    create_res = await client.post(
        "/api/v1/shared/api-keys", json={"name": "Revokable Key"}, headers=headers
    )
    key_id = create_res.json()["id"]

    del_res = await client.delete(f"/api/v1/shared/api-keys/{key_id}", headers=headers)
    assert del_res.status_code == 200

    # Listeleme → boş olmalı
    list_res = await client.get("/api/v1/shared/api-keys", headers=headers)
    assert list_res.json() == []


@pytest.mark.asyncio
async def test_authenticate_with_api_key(client: AsyncClient) -> None:
    """X-API-Key header ile endpoint'e erişim."""
    headers = await _register_and_login(client, "apikey_auth@example.com")
    create_res = await client.post(
        "/api/v1/shared/api-keys",
        json={"name": "Auth Key", "scopes": ["profile:view"]},
        headers=headers,
    )
    raw_key = create_res.json()["key"]

    # API Key ile /users/me erişimi
    res = await client.get("/api/v1/shared/me", headers={"X-API-Key": raw_key})
    assert res.status_code == 200
    assert res.json()["email"] == "apikey_auth@example.com"


@pytest.mark.asyncio
async def test_invalid_api_key_rejected(client: AsyncClient) -> None:
    """test_invalid_api_key_rejected senaryosunu test eder."""
    res = await client.get("/api/v1/shared/me", headers={"X-API-Key": "sk_live_invalid"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_revoke_other_users_key_fails(client: AsyncClient) -> None:
    """test_revoke_other_users_key_fails senaryosunu test eder."""
    headers1 = await _register_and_login(client, "apikey_own1@example.com")
    headers2 = await _register_and_login(client, "apikey_own2@example.com")

    create_res = await client.post(
        "/api/v1/shared/api-keys", json={"name": "User1 Key"}, headers=headers1
    )
    key_id = create_res.json()["id"]

    # User2 User1'in key'ini silmeye çalışıyor
    del_res = await client.delete(f"/api/v1/shared/api-keys/{key_id}", headers=headers2)
    assert del_res.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Notifications
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_notifications_empty_by_default(client: AsyncClient) -> None:
    """test_notifications_empty_by_default senaryosunu test eder."""
    headers = await _register_and_login(client, "notif_empty@example.com")
    res = await client.get("/api/v1/shared/notifications", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_notification_create_and_list(client: AsyncClient, db_session: object) -> None:
    """Servis üzerinden bildirim oluştur, endpoint ile listele."""
    from uuid import UUID

    from app.services.notification import NotificationService

    headers = await _register_and_login(client, "notif_list@example.com")
    user_res = await client.get("/api/v1/shared/me", headers=headers)
    user_id = UUID(user_res.json()["id"])

    # Servis üzerinden bildirim oluştur (WS push'u mock'la)
    with patch(
        "app.services.notification.NotificationService._push_to_websocket", new_callable=AsyncMock
    ):
        svc = NotificationService(db_session)  # type: ignore[arg-type]
        await svc.create(user_id, "Test Bildirimi", body="İçerik")

    res = await client.get("/api/v1/shared/notifications", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Test Bildirimi"
    assert data["items"][0]["is_read"] is False


@pytest.mark.asyncio
async def test_notification_mark_read(client: AsyncClient, db_session: object) -> None:
    """test_notification_mark_read senaryosunu test eder."""
    from uuid import UUID

    from app.services.notification import NotificationService

    headers = await _register_and_login(client, "notif_read@example.com")
    user_res = await client.get("/api/v1/shared/me", headers=headers)
    user_id = UUID(user_res.json()["id"])

    with patch(
        "app.services.notification.NotificationService._push_to_websocket", new_callable=AsyncMock
    ):
        svc = NotificationService(db_session)  # type: ignore[arg-type]
        notif = await svc.create(user_id, "Okunacak Bildirim")

    # Mark as read
    res = await client.patch(f"/api/v1/shared/notifications/{notif.id}", headers=headers)
    assert res.status_code == 200
    assert res.json()["is_read"] is True


@pytest.mark.asyncio
async def test_notification_mark_all_read(client: AsyncClient, db_session: object) -> None:
    """test_notification_mark_all_read senaryosunu test eder."""
    from uuid import UUID

    from app.services.notification import NotificationService

    headers = await _register_and_login(client, "notif_readall@example.com")
    user_res = await client.get("/api/v1/shared/me", headers=headers)
    user_id = UUID(user_res.json()["id"])

    with patch(
        "app.services.notification.NotificationService._push_to_websocket", new_callable=AsyncMock
    ):
        svc = NotificationService(db_session)  # type: ignore[arg-type]
        await svc.create(user_id, "Bildirim 1")
        await svc.create(user_id, "Bildirim 2")

    res = await client.patch("/api/v1/shared/notifications/read-all", headers=headers)
    assert res.status_code == 200

    # Unread count → 0
    count_res = await client.get("/api/v1/shared/notifications/unread-count", headers=headers)
    assert count_res.json()["count"] == 0


@pytest.mark.asyncio
async def test_notification_delete(client: AsyncClient, db_session: object) -> None:
    """test_notification_delete senaryosunu test eder."""
    from uuid import UUID

    from app.services.notification import NotificationService

    headers = await _register_and_login(client, "notif_delete@example.com")
    user_res = await client.get("/api/v1/shared/me", headers=headers)
    user_id = UUID(user_res.json()["id"])

    with patch(
        "app.services.notification.NotificationService._push_to_websocket", new_callable=AsyncMock
    ):
        svc = NotificationService(db_session)  # type: ignore[arg-type]
        notif = await svc.create(user_id, "Silinecek Bildirim")

    del_res = await client.delete(f"/api/v1/shared/notifications/{notif.id}", headers=headers)
    assert del_res.status_code == 200

    # Listeleme → boş
    list_res = await client.get("/api/v1/shared/notifications", headers=headers)
    assert list_res.json()["total"] == 0


@pytest.mark.asyncio
async def test_notification_unread_count(client: AsyncClient, db_session: object) -> None:
    """test_notification_unread_count senaryosunu test eder."""
    from uuid import UUID

    from app.services.notification import NotificationService

    headers = await _register_and_login(client, "notif_count@example.com")
    user_res = await client.get("/api/v1/shared/me", headers=headers)
    user_id = UUID(user_res.json()["id"])

    with patch(
        "app.services.notification.NotificationService._push_to_websocket", new_callable=AsyncMock
    ):
        svc = NotificationService(db_session)  # type: ignore[arg-type]
        await svc.create(user_id, "A")
        await svc.create(user_id, "B")
        await svc.create(user_id, "C")

    res = await client.get("/api/v1/shared/notifications/unread-count", headers=headers)
    assert res.json()["count"] == 3


# ═══════════════════════════════════════════════════════════════════════════════
# Health Check Endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_health_live(client: AsyncClient) -> None:
    """test_health_live senaryosunu test eder."""
    res = await client.get("/health/live")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_ready_returns_200_or_503(client: AsyncClient) -> None:
    """Test ortamında storage olmayabilir — 200 veya 503 kabul edilir."""
    res = await client.get("/health/ready")
    assert res.status_code in (200, 503)


# ═══════════════════════════════════════════════════════════════════════════════
# API Key — Ek Senaryolar
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_api_key_with_past_expiry_rejected(client: AsyncClient) -> None:
    """expires_at geçmişte olan key ile auth → 401."""
    headers = await _register_and_login(client, "apikey_expired@example.com")

    # Geçmişte bir tarih ile key oluştur
    past_date = "2020-01-01T00:00:00Z"
    create_res = await client.post(
        "/api/v1/shared/api-keys",
        json={"name": "Expired Key", "expires_at": past_date, "scopes": ["profile:view"]},
        headers=headers,
    )
    assert create_res.status_code == 201
    raw_key = create_res.json()["key"]

    # Süresi dolmuş key ile endpoint'e erişim → 401
    res = await client.get("/api/v1/shared/me", headers={"X-API-Key": raw_key})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_api_key_with_future_expiry_accepted(client: AsyncClient) -> None:
    """expires_at gelecekte olan key ile auth → 200."""
    headers = await _register_and_login(client, "apikey_future@example.com")

    future_date = "2099-12-31T23:59:59Z"
    create_res = await client.post(
        "/api/v1/shared/api-keys",
        json={"name": "Future Key", "expires_at": future_date, "scopes": ["profile:view"]},
        headers=headers,
    )
    assert create_res.status_code == 201
    raw_key = create_res.json()["key"]

    res = await client.get("/api/v1/shared/me", headers={"X-API-Key": raw_key})
    assert res.status_code == 200
    assert res.json()["email"] == "apikey_future@example.com"


# ═══════════════════════════════════════════════════════════════════════════════
# Notifications — Sahiplik Kontrolü
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_mark_other_users_notification_as_read_returns_404(
    client: AsyncClient, db_session: object
) -> None:
    """Başka kullanıcının bildirimini okundu işaretlemeye çalışmak → 404."""
    from unittest.mock import AsyncMock, patch
    from uuid import UUID

    from app.services.notification import NotificationService

    headers1 = await _register_and_login(client, "notif_own1@example.com")
    headers2 = await _register_and_login(client, "notif_own2@example.com")

    user1_res = await client.get("/api/v1/shared/me", headers=headers1)
    user1_id = UUID(user1_res.json()["id"])

    with patch(
        "app.services.notification.NotificationService._push_to_websocket",
        new_callable=AsyncMock,
    ):
        svc = NotificationService(db_session)  # type: ignore[arg-type]
        notif = await svc.create(user1_id, "User1'e ait bildirim")

    # User2, User1'in bildirimini okumaya çalışıyor → 404
    res = await client.patch(f"/api/v1/shared/notifications/{notif.id}", headers=headers2)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_delete_other_users_notification_returns_404(
    client: AsyncClient, db_session: object
) -> None:
    """Başka kullanıcının bildirimini silmeye çalışmak → 404."""
    from unittest.mock import AsyncMock, patch
    from uuid import UUID

    from app.services.notification import NotificationService

    headers1 = await _register_and_login(client, "notif_delown1@example.com")
    headers2 = await _register_and_login(client, "notif_delown2@example.com")

    user1_res = await client.get("/api/v1/shared/me", headers=headers1)
    user1_id = UUID(user1_res.json()["id"])

    with patch(
        "app.services.notification.NotificationService._push_to_websocket",
        new_callable=AsyncMock,
    ):
        svc = NotificationService(db_session)  # type: ignore[arg-type]
        notif = await svc.create(user1_id, "User1'e ait silinecek bildirim")

    # User2, User1'in bildirimini silmeye çalışıyor → 404
    res = await client.delete(f"/api/v1/shared/notifications/{notif.id}", headers=headers2)
    assert res.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# TOTP — Backup Code Login
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_login_with_totp_backup_code(client: AsyncClient) -> None:
    """TOTP aktifken backup kod ile login yapılabilmeli (tek kullanımlık)."""
    import pyotp

    email = "totp_backup@example.com"
    password = "StrongPass1"
    headers = await _register_and_login(client, email, password)

    # TOTP kur ve etkinleştir
    setup_res = await client.post("/api/v1/shared/auth/totp/setup", headers=headers)
    secret = setup_res.json()["secret"]
    valid_code = pyotp.TOTP(secret).now()
    verify_res = await client.post(
        "/api/v1/shared/auth/totp/verify", json={"code": valid_code}, headers=headers
    )
    assert verify_res.status_code == 200
    backup_codes: list[str] = verify_res.json()["backup_codes"]
    assert len(backup_codes) == 8

    # Login → partial_token, sonra backup kod ile challenge → 200
    partial_res = await client.post(
        "/api/v1/client/auth/login", json={"email": email, "password": password}
    )
    assert partial_res.json()["requires_totp"] is True
    partial = partial_res.json()["partial_token"]

    res = await client.post(
        "/api/v1/shared/auth/totp-challenge",
        json={"partial_token": partial, "code": backup_codes[0]},
    )
    assert res.status_code == 200
    assert "access_token" in res.json()

    # Aynı backup kod ikinci kez kullanılamaz — yeni partial_token gerekli
    partial_res2 = await client.post(
        "/api/v1/client/auth/login", json={"email": email, "password": password}
    )
    partial2 = partial_res2.json()["partial_token"]
    res2 = await client.post(
        "/api/v1/shared/auth/totp-challenge",
        json={"partial_token": partial2, "code": backup_codes[0]},
    )
    assert res2.status_code == 401
