"""Roles endpoint testleri — /api/v1/admin/roles"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fakeredis.aioredis import FakeRedis
from sqlalchemy import update as sa_update

from app.api.dependencies.auth import get_user_permissions
from app.core.permissions import Permission
from app.db.models.role import Role
from app.db.models.user import SurfaceType, User

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

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


async def _promote_to_admin(db_session: AsyncSession, email: str) -> None:
    from sqlalchemy import select

    result = await db_session.execute(select(Role.id).where(Role.name == "admin"))
    admin_role_id = result.scalar_one()
    await db_session.execute(
        sa_update(User)
        .where(User.email == email)
        .values(role_id=admin_role_id, surface=SurfaceType.ADMIN.value)
    )
    await db_session.commit()
    db_session.expire_all()


# ── GET /roles ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_roles_as_admin(client: AsyncClient, db_session: AsyncSession):
    """Admin tüm rolleri listeleyebilmeli."""
    admin_email = "admin_list_roles@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.get("/api/v1/admin/roles", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 3  # admin, user, moderator seed edilmiş
    names = {r["name"] for r in data}
    assert {"admin", "user", "moderator"}.issubset(names)


@pytest.mark.asyncio
async def test_list_roles_response_structure(client: AsyncClient, db_session: AsyncSession):
    """Rol response'u beklenen alanları içermeli."""
    admin_email = "admin_roles_struct@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.get("/api/v1/admin/roles", headers=headers)

    assert res.status_code == 200
    role = res.json()[0]
    assert "id" in role
    assert "name" in role
    assert "description" in role
    assert "is_system" in role
    assert "permissions" in role
    assert isinstance(role["permissions"], list)


@pytest.mark.asyncio
async def test_list_roles_as_non_admin(client: AsyncClient):
    """Non-admin rol listesine erişememeli."""
    headers = await _auth_headers(client, "non_admin_roles@example.com")
    res = await client.get("/api/v1/admin/roles", headers=headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_list_roles_unauthorized(client: AsyncClient):
    """Token olmadan rol listesine erişilememeli."""
    res = await client.get("/api/v1/admin/roles")
    assert res.status_code == 401


# ── POST /roles ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_role_as_admin(client: AsyncClient, db_session: AsyncSession):
    """Admin yeni özel rol oluşturabilmeli."""
    admin_email = "admin_create_role@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.post(
        "/api/v1/admin/roles",
        json={"name": "accountant", "description": "Muhasebe rolü", "permissions": []},
        headers=headers,
    )

    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "accountant"
    assert data["description"] == "Muhasebe rolü"
    assert data["is_system"] is False


@pytest.mark.asyncio
async def test_create_role_with_permissions(client: AsyncClient, db_session: AsyncSession):
    """Permission listesi ile rol oluşturulabilmeli."""
    admin_email = "admin_create_role_perm@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.post(
        "/api/v1/admin/roles",
        json={
            "name": "reporter",
            "description": "Rapor rolü",
            "permissions": ["audit:read", "users:read"],
        },
        headers=headers,
    )

    assert res.status_code == 201
    data = res.json()
    assert "audit:read" in data["permissions"]
    assert "users:read" in data["permissions"]


@pytest.mark.asyncio
async def test_create_role_duplicate_name_fails(client: AsyncClient, db_session: AsyncSession):
    """Aynı isimde iki rol oluşturulamaz."""
    admin_email = "admin_dup_role@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    payload = {"name": "duplicate_role", "description": "İlk", "permissions": []}
    await client.post("/api/v1/admin/roles", json=payload, headers=headers)

    res = await client.post("/api/v1/admin/roles", json=payload, headers=headers)
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_create_role_invalid_name_format(client: AsyncClient, db_session: AsyncSession):
    """Geçersiz isim formatı (büyük harf, boşluk) → 422."""
    admin_email = "admin_invalid_role_name@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.post(
        "/api/v1/admin/roles",
        json={"name": "Invalid Role", "description": None, "permissions": []},
        headers=headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_role_as_non_admin(client: AsyncClient):
    """Non-admin rol oluşturamamalı."""
    headers = await _auth_headers(client, "non_admin_create_role@example.com")
    res = await client.post(
        "/api/v1/admin/roles",
        json={"name": "nope", "description": None, "permissions": []},
        headers=headers,
    )
    assert res.status_code == 403


# ── GET /roles/{id} ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_role_by_id(client: AsyncClient, db_session: AsyncSession):
    """Admin ID ile rol getirebilmeli."""
    admin_email = "admin_get_role@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    # Önce listeyi al, bir rol ID'si seç
    roles = (await client.get("/api/v1/admin/roles", headers=headers)).json()
    target = next(r for r in roles if r["name"] == "user")

    res = await client.get(f"/api/v1/admin/roles/{target['id']}", headers=headers)

    assert res.status_code == 200
    assert res.json()["name"] == "user"
    assert res.json()["is_system"] is True


@pytest.mark.asyncio
async def test_get_role_not_found(client: AsyncClient, db_session: AsyncSession):
    """Var olmayan rol ID → 404."""
    admin_email = "admin_role_404@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.get(
        "/api/v1/admin/roles/00000000-0000-0000-0000-000000000000", headers=headers
    )
    assert res.status_code == 404


# ── PATCH /roles/{id} ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_custom_role_description(client: AsyncClient, db_session: AsyncSession):
    """Özel rolün açıklaması güncellenebilmeli."""
    admin_email = "admin_update_role@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    create_res = await client.post(
        "/api/v1/admin/roles",
        json={"name": "updatable_role", "description": "Eski açıklama", "permissions": []},
        headers=headers,
    )
    role_id = create_res.json()["id"]

    res = await client.patch(
        f"/api/v1/admin/roles/{role_id}",
        json={"description": "Yeni açıklama"},
        headers=headers,
    )

    assert res.status_code == 200
    assert res.json()["description"] == "Yeni açıklama"


@pytest.mark.asyncio
async def test_update_custom_role_permissions(client: AsyncClient, db_session: AsyncSession):
    """Özel rolün permission seti güncellenebilmeli."""
    admin_email = "admin_update_perms@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    create_res = await client.post(
        "/api/v1/admin/roles",
        json={"name": "perm_update_role", "description": None, "permissions": ["users:read"]},
        headers=headers,
    )
    role_id = create_res.json()["id"]

    res = await client.patch(
        f"/api/v1/admin/roles/{role_id}",
        json={"permissions": ["audit:read", "users:read"]},
        headers=headers,
    )

    assert res.status_code == 200
    perms = res.json()["permissions"]
    assert "audit:read" in perms
    assert "users:read" in perms


@pytest.mark.asyncio
async def test_update_system_role_permissions_fails(client: AsyncClient, db_session: AsyncSession):
    """Sistem rolünün permission seti değiştirilemez."""
    admin_email = "admin_sys_perm_update@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    roles = (await client.get("/api/v1/admin/roles", headers=headers)).json()
    user_role = next(r for r in roles if r["name"] == "user")

    res = await client.patch(
        f"/api/v1/admin/roles/{user_role['id']}",
        json={"permissions": ["admin:panel_access"]},
        headers=headers,
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_update_system_role_description_allowed(
    client: AsyncClient, db_session: AsyncSession
):
    """Sistem rolünün açıklaması güncellenebilmeli."""
    admin_email = "admin_sys_desc_update@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    roles = (await client.get("/api/v1/admin/roles", headers=headers)).json()
    moderator_role = next(r for r in roles if r["name"] == "moderator")

    res = await client.patch(
        f"/api/v1/admin/roles/{moderator_role['id']}",
        json={"description": "Güncellenmiş açıklama"},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["description"] == "Güncellenmiş açıklama"


# ── DELETE /roles/{id} ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_custom_role(client: AsyncClient, db_session: AsyncSession):
    """Admin özel rolü silebilmeli."""
    admin_email = "admin_delete_role@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    create_res = await client.post(
        "/api/v1/admin/roles",
        json={"name": "deletable_role", "description": None, "permissions": []},
        headers=headers,
    )
    role_id = create_res.json()["id"]

    res = await client.delete(f"/api/v1/admin/roles/{role_id}", headers=headers)
    assert res.status_code == 200

    # Artık bulunamaz
    res_get = await client.get(f"/api/v1/admin/roles/{role_id}", headers=headers)
    assert res_get.status_code == 404


@pytest.mark.asyncio
async def test_delete_system_role_fails(client: AsyncClient, db_session: AsyncSession):
    """Sistem rolleri silinemez."""
    admin_email = "admin_del_sys_role@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    roles = (await client.get("/api/v1/admin/roles", headers=headers)).json()
    admin_role = next(r for r in roles if r["name"] == "admin")

    res = await client.delete(f"/api/v1/admin/roles/{admin_role['id']}", headers=headers)
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_delete_nonexistent_role(client: AsyncClient, db_session: AsyncSession):
    """Var olmayan rol silmeye çalışmak → 404."""
    admin_email = "admin_del_404@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.delete(
        "/api/v1/admin/roles/00000000-0000-0000-0000-000000000000", headers=headers
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_update_role_permissions_invalidates_assigned_user_cache(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: FakeRedis,
):
    """Role permission değişikliğinde atanmış kullanıcının permission cache'i temizlenmeli."""
    admin_email = "admin_role_cache_update@example.com"
    target_email = "role_cache_target@example.com"

    target_headers = await _auth_headers(client, target_email)
    target_id = (await client.get("/api/v1/shared/me", headers=target_headers)).json()["id"]

    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    create_res = await client.post(
        "/api/v1/admin/roles",
        json={
            "name": "cache_role",
            "description": "Cache role",
            "permissions": ["notifications:read"],
        },
        headers=headers,
    )
    role_id = create_res.json()["id"]

    assign_res = await client.patch(
        f"/api/v1/admin/users/{target_id}/role",
        json={"role_name": "cache_role"},
        headers=headers,
    )
    assert assign_res.status_code == 200

    perms_before = await get_user_permissions(target_id)
    assert Permission.NOTIFICATIONS_READ.value in perms_before
    assert await fake_redis.keys(f"user_permissions:{target_id}") != []

    update_res = await client.patch(
        f"/api/v1/admin/roles/{role_id}",
        json={"permissions": ["api_keys:read"]},
        headers=headers,
    )
    assert update_res.status_code == 200

    perms_after = await get_user_permissions(target_id)
    assert Permission.NOTIFICATIONS_READ.value not in perms_after
    assert Permission.API_KEYS_READ.value in perms_after


@pytest.mark.asyncio
async def test_delete_role_as_non_admin(client: AsyncClient, db_session: AsyncSession):
    """Non-admin rol silemez."""
    admin_email = "admin_for_del_perm@example.com"
    headers_admin = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    create_res = await client.post(
        "/api/v1/admin/roles",
        json={"name": "del_perm_role", "description": None, "permissions": []},
        headers=headers_admin,
    )
    role_id = create_res.json()["id"]

    headers_non_admin = await _auth_headers(client, "non_admin_del_role@example.com")
    res = await client.delete(f"/api/v1/admin/roles/{role_id}", headers=headers_non_admin)
    assert res.status_code == 403
