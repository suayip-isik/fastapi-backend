"""
E2E test: Admin kullanıcı yönetimi yolculuğu.

Kayıt → admin yükseltme → kullanıcı listeleme → kullanıcı getirme → deaktif etme → giriş reddi
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import update as sa_update

from app.core.system_roles import PANEL_ADMIN_ROLE
from app.db.models.role import Role
from app.db.models.user import SurfaceType, User

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_full_user_management_journey(client: AsyncClient, db_session: AsyncSession) -> None:
    """
    Adım 1: Sıradan kullanıcı kaydı → 201
    Adım 2: Admin kullanıcı kaydı → 201
    Adım 3: Admin rolüne yükselt (db_session ile)
    Adım 4: Admin girişi → 200
    Adım 5: Admin tüm kullanıcıları listeler → 200, toplam >= 2
    Adım 6: Admin sıradan kullanıcıyı ID ile getirir → 200, email eşleşmeli
    Adım 7: Admin sıradan kullanıcıyı deaktif eder → 200
    Adım 8: Deaktif kullanıcı giriş yapamaz → 401
    Adım 9: Admin deaktif kullanıcıyı getirir → 200, is_active=False
    """
    user_email = "journey_user@example.com"
    admin_email = "journey_admin@example.com"
    password = "StrongPass1"

    # Adım 1: Sıradan kullanıcı kaydı
    reg_user = await client.post(
        "/api/v1/client/auth/register", json={"email": user_email, "password": password}
    )
    assert reg_user.status_code == 201
    user_id = reg_user.json()["id"]

    # Adım 2: Admin kullanıcı kaydı
    await client.post(
        "/api/v1/client/auth/register", json={"email": admin_email, "password": password}
    )

    # Adım 3: Admin rolüne yükselt
    from sqlalchemy import select

    result = await db_session.execute(select(Role.id).where(Role.name == PANEL_ADMIN_ROLE))
    admin_role_id = result.scalar_one()
    await db_session.execute(
        sa_update(User)
        .where(User.email == admin_email)
        .values(role_id=admin_role_id, surface=SurfaceType.ADMIN.value)
    )
    await db_session.commit()
    db_session.expire_all()

    # Adım 4: Admin girişi
    admin_login = await client.post(
        "/api/v1/admin/auth/login", json={"email": admin_email, "password": password}
    )
    assert admin_login.status_code == 200
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    # Adım 5: Kullanıcı listesi
    users_list = await client.get("/api/v1/admin/users", headers=admin_headers)
    assert users_list.status_code == 200
    assert users_list.json()["total"] >= 2

    # Adım 6: Sıradan kullanıcıyı ID ile getir
    get_user = await client.get(f"/api/v1/admin/users/{user_id}", headers=admin_headers)
    assert get_user.status_code == 200
    assert get_user.json()["email"] == user_email
    assert get_user.json()["is_active"] is True

    # Adım 7: Kullanıcıyı soft-delete ile sil
    deact = await client.delete(
        f"/api/v1/admin/users/{user_id}",
        headers={**admin_headers, "Accept-Language": "tr"},
    )
    assert deact.status_code == 200
    assert "silindi" in deact.json()["message"]

    # Adım 8: Silinmiş kullanıcı giriş yapamaz
    bad_login = await client.post(
        "/api/v1/client/auth/login", json={"email": user_email, "password": password}
    )
    assert bad_login.status_code == 401

    # Adım 9: Admin silinmiş kullanıcıyı artık göremez (404)
    get_deact = await client.get(f"/api/v1/admin/users/{user_id}", headers=admin_headers)
    assert get_deact.status_code == 404

    # Ek: Admin olmayan kullanıcı listeyi göremez
    await client.post("/api/v1/admin/auth/login", json={"email": admin_email, "password": password})
    non_admin_login = await client.post(
        "/api/v1/client/auth/register",
        json={"email": "journey_nonadmin@example.com", "password": password},
    )
    assert non_admin_login.status_code == 201
    non_admin_auth = await client.post(
        "/api/v1/client/auth/login",
        json={"email": "journey_nonadmin@example.com", "password": password},
    )
    non_admin_headers = {"Authorization": f"Bearer {non_admin_auth.json()['access_token']}"}
    forbidden = await client.get("/api/v1/admin/users", headers=non_admin_headers)
    assert forbidden.status_code == 403

    # Ek: Var olmayan kullanıcı için 404
    nonexistent = await client.get(
        "/api/v1/admin/users/00000000-0000-0000-0000-000000000000", headers=admin_headers
    )
    assert nonexistent.status_code == 404
