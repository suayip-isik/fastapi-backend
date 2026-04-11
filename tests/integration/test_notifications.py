"""Notifications endpoint testleri — /api/v1/shared/notifications"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.notification import NotificationType
from app.db.repositories.notification import NotificationRepository

if TYPE_CHECKING:
    from httpx import AsyncClient

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _register_and_login(
    client: AsyncClient, email: str, password: str = "StrongPass1"
) -> dict:
    await client.post("/api/v1/client/auth/register", json={"email": email, "password": password})
    res = await client.post(
        "/api/v1/client/auth/login", json={"email": email, "password": password}
    )
    return res.json()


async def _auth_headers(client: AsyncClient, email: str, password: str = "StrongPass1") -> dict:
    tokens = await _register_and_login(client, email, password)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _create_notification_direct(
    db_session: AsyncSession,
    user_id: str,
    title: str = "Test Bildirimi",
    *,
    is_read: bool = False,
) -> str:
    """Veritabanına doğrudan bildirim ekler (service bypass)."""
    from uuid import UUID

    repo = NotificationRepository(db_session)
    notif = await repo.create(
        user_id=UUID(user_id),
        type=NotificationType.INFO,
        title=title,
        body="Test içeriği",
    )
    await db_session.commit()
    return str(notif.id)


# ── GET /notifications ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_notifications_empty(client: AsyncClient):
    """Hiç bildirim yokken boş sayfalı liste döner."""
    headers = await _auth_headers(client, "notif_list_empty@example.com")

    res = await client.get("/api/v1/shared/notifications", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_notifications_returns_own(client: AsyncClient, db_session: AsyncSession):
    """Kullanıcı sadece kendi bildirimlerini görür."""
    tokens = await _register_and_login(client, "notif_list_own@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    user_id = (await client.get("/api/v1/shared/me", headers=headers)).json()["id"]

    await _create_notification_direct(db_session, user_id, "Bildirim 1")
    await _create_notification_direct(db_session, user_id, "Bildirim 2")

    res = await client.get("/api/v1/shared/notifications", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    titles = {n["title"] for n in data["items"]}
    assert "Bildirim 1" in titles
    assert "Bildirim 2" in titles


@pytest.mark.asyncio
async def test_list_notifications_pagination(client: AsyncClient, db_session: AsyncSession):
    """Sayfalama parametreleri çalışmalı."""
    tokens = await _register_and_login(client, "notif_paginate@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    user_id = (await client.get("/api/v1/shared/me", headers=headers)).json()["id"]

    for i in range(5):
        await _create_notification_direct(db_session, user_id, f"Bildirim {i}")

    res = await client.get("/api/v1/shared/notifications?page=1&size=3", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 5
    assert len(data["items"]) == 3


@pytest.mark.asyncio
async def test_list_notifications_unauthorized(client: AsyncClient):
    """Token olmadan bildirimler alınamaz."""
    res = await client.get("/api/v1/shared/notifications")
    assert res.status_code == 401


# ── GET /notifications/unread-count ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_unread_count_zero(client: AsyncClient):
    """Hiç bildirim yokken okunmamış sayısı 0 olmalı."""
    headers = await _auth_headers(client, "notif_count_zero@example.com")

    res = await client.get("/api/v1/shared/notifications/unread-count", headers=headers)

    assert res.status_code == 200
    assert res.json()["count"] == 0


@pytest.mark.asyncio
async def test_unread_count_reflects_unread(client: AsyncClient, db_session: AsyncSession):
    """Okunmamış bildirim sayısı doğru hesaplanmalı."""
    tokens = await _register_and_login(client, "notif_count_unread@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    user_id = (await client.get("/api/v1/shared/me", headers=headers)).json()["id"]

    for i in range(3):
        await _create_notification_direct(db_session, user_id, f"Bildirim {i}")

    res = await client.get("/api/v1/shared/notifications/unread-count", headers=headers)

    assert res.status_code == 200
    assert res.json()["count"] == 3


# ── PATCH /notifications/{id} ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mark_notification_read(client: AsyncClient, db_session: AsyncSession):
    """Bildirim okundu olarak işaretlenebilmeli."""
    tokens = await _register_and_login(client, "notif_mark_read@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    user_id = (await client.get("/api/v1/shared/me", headers=headers)).json()["id"]
    notif_id = await _create_notification_direct(db_session, user_id, "Okunacak Bildirim")

    res = await client.patch(f"/api/v1/shared/notifications/{notif_id}", headers=headers)

    assert res.status_code == 200
    assert res.json()["is_read"] is True


@pytest.mark.asyncio
async def test_mark_notification_read_decreases_unread_count(
    client: AsyncClient, db_session: AsyncSession
):
    """Okundu işaretlemek unread count'u düşürmeli."""
    tokens = await _register_and_login(client, "notif_read_count@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    user_id = (await client.get("/api/v1/shared/me", headers=headers)).json()["id"]

    notif_id = await _create_notification_direct(db_session, user_id, "Sayaç Bildirimi")

    count_before = (
        await client.get("/api/v1/shared/notifications/unread-count", headers=headers)
    ).json()["count"]
    await client.patch(f"/api/v1/shared/notifications/{notif_id}", headers=headers)
    count_after = (
        await client.get("/api/v1/shared/notifications/unread-count", headers=headers)
    ).json()["count"]

    assert count_after == count_before - 1


@pytest.mark.asyncio
async def test_mark_other_users_notification_fails(client: AsyncClient, db_session: AsyncSession):
    """Başka kullanıcının bildirimini okundu işaretleyemez."""
    tokens_a = await _register_and_login(client, "notif_cross_a@example.com")
    headers_a = {"Authorization": f"Bearer {tokens_a['access_token']}"}
    user_a_id = (await client.get("/api/v1/shared/me", headers=headers_a)).json()["id"]

    headers_b = await _auth_headers(client, "notif_cross_b@example.com")

    notif_id = await _create_notification_direct(db_session, user_a_id, "A'nın Bildirimi")

    res = await client.patch(f"/api/v1/shared/notifications/{notif_id}", headers=headers_b)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_mark_nonexistent_notification_fails(client: AsyncClient):
    """Var olmayan bildirimi okundu işaretleme → 404."""
    headers = await _auth_headers(client, "notif_mark_404@example.com")

    res = await client.patch(f"/api/v1/shared/notifications/{uuid4()}", headers=headers)
    assert res.status_code == 404


# ── PATCH /notifications/read-all ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mark_all_read(client: AsyncClient, db_session: AsyncSession):
    """Tüm bildirimler okundu olarak işaretlenebilmeli."""
    tokens = await _register_and_login(client, "notif_read_all@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    user_id = (await client.get("/api/v1/shared/me", headers=headers)).json()["id"]

    for i in range(3):
        await _create_notification_direct(db_session, user_id, f"Bildirim {i}")

    res = await client.patch("/api/v1/shared/notifications/read-all", headers=headers)

    assert res.status_code == 200
    count_res = await client.get("/api/v1/shared/notifications/unread-count", headers=headers)
    assert count_res.json()["count"] == 0


@pytest.mark.asyncio
async def test_mark_all_read_empty(client: AsyncClient):
    """Bildirim yokken read-all çağrısı hata vermemeli."""
    headers = await _auth_headers(client, "notif_read_all_empty@example.com")

    res = await client.patch("/api/v1/shared/notifications/read-all", headers=headers)
    assert res.status_code == 200


# ── DELETE /notifications/{id} ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_notification_success(client: AsyncClient, db_session: AsyncSession):
    """Bildirim başarıyla silinebilmeli."""
    tokens = await _register_and_login(client, "notif_delete@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    user_id = (await client.get("/api/v1/shared/me", headers=headers)).json()["id"]
    notif_id = await _create_notification_direct(db_session, user_id, "Silinecek Bildirim")

    res = await client.delete(f"/api/v1/shared/notifications/{notif_id}", headers=headers)

    assert res.status_code == 200
    # Artık listede olmamalı
    list_res = await client.get("/api/v1/shared/notifications", headers=headers)
    assert list_res.json()["total"] == 0


@pytest.mark.asyncio
async def test_delete_other_users_notification_fails(client: AsyncClient, db_session: AsyncSession):
    """Başka kullanıcının bildirimi silinemez."""
    tokens_a = await _register_and_login(client, "notif_del_cross_a@example.com")
    headers_a = {"Authorization": f"Bearer {tokens_a['access_token']}"}
    user_a_id = (await client.get("/api/v1/shared/me", headers=headers_a)).json()["id"]

    headers_b = await _auth_headers(client, "notif_del_cross_b@example.com")

    notif_id = await _create_notification_direct(db_session, user_a_id, "A'nın Bildirimi")

    res = await client.delete(f"/api/v1/shared/notifications/{notif_id}", headers=headers_b)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_notification_fails(client: AsyncClient):
    """Var olmayan bildirim silme → 404."""
    headers = await _auth_headers(client, "notif_del_404@example.com")

    res = await client.delete(f"/api/v1/shared/notifications/{uuid4()}", headers=headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_delete_notification_unauthorized(client: AsyncClient):
    """Token olmadan bildirim silinemez."""
    res = await client.delete(f"/api/v1/shared/notifications/{uuid4()}")
    assert res.status_code == 401
