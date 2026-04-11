"""Users endpoint testleri — /api/v1/admin/users/"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select
from sqlalchemy import update as sa_update

from app.core.permissions import Permission
from app.db.models.audit_log import AuditAction
from app.db.models.role import Role, RolePermission
from app.db.models.user import SurfaceType, User

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
    await client.post("/api/v1/client/auth/register", json={"email": email, "password": password})
    res = await client.post(
        "/api/v1/client/auth/login", json={"email": email, "password": password}
    )
    return res.json()


async def _auth_headers(client: AsyncClient, email: str, password: str = "StrongPass1") -> dict:
    """Yardımcı fonksiyon."""
    tokens = await _register_and_login(client, email, password)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _promote_to_admin(db_session: AsyncSession, email: str) -> None:
    """Kullanıcıyı ADMIN rolüne yükselt ve commit et.

    get_user_permissions() ayrı bir permission provider / session scope kullanır;
    commit olmadan yeni role_id'yi göremez.
    """
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


async def _promote_to_admin_surface_role(
    db_session: AsyncSession,
    *,
    email: str,
    role_name: str,
    permissions: list[Permission],
) -> None:
    """Kullanıcıyı admin surface'e taşıyıp özel role ata."""
    role = await db_session.scalar(select(Role).where(Role.name == role_name))
    if role is None:
        role = Role(name=role_name, description=role_name, is_system=False)
        db_session.add(role)
        await db_session.flush()
        for permission in permissions:
            db_session.add(RolePermission(role_id=role.id, permission=permission.value))
    await db_session.execute(
        sa_update(User)
        .where(User.email == email)
        .values(role_id=role.id, surface=SurfaceType.ADMIN.value)
    )
    await db_session.commit()
    db_session.expire_all()


# ── GET /users/me ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_users_me(client: AsyncClient):
    """test_get_users_me senaryosunu test eder."""
    headers = await _auth_headers(client, "users_me@example.com")
    res = await client.get("/api/v1/shared/me", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "users_me@example.com"
    assert "id" in data
    assert data["is_active"] is True
    assert data["role"]["name"] == "user"


@pytest.mark.asyncio
async def test_get_users_me_unauthorized(client: AsyncClient):
    """test_get_users_me_unauthorized senaryosunu test eder."""
    res = await client.get("/api/v1/shared/me")
    assert res.status_code == 401


# ── PATCH /users/me ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_me_full_name(client: AsyncClient):
    """test_update_me_full_name senaryosunu test eder."""
    headers = await _auth_headers(client, "update_name@example.com")
    res = await client.patch(
        "/api/v1/shared/me", json={"full_name": "Yeni Ad Soyad"}, headers=headers
    )

    assert res.status_code == 200
    assert res.json()["full_name"] == "Yeni Ad Soyad"


@pytest.mark.asyncio
async def test_update_me_username(client: AsyncClient):
    """test_update_me_username senaryosunu test eder."""
    headers = await _auth_headers(client, "update_username@example.com")
    res = await client.patch(
        "/api/v1/shared/me", json={"username": "yeni_kullanici"}, headers=headers
    )

    assert res.status_code == 200
    assert res.json()["username"] == "yeni_kullanici"


@pytest.mark.asyncio
async def test_update_me_email(client: AsyncClient):
    """test_update_me_email senaryosunu test eder."""
    headers = await _auth_headers(client, "old_email@example.com")
    res = await client.patch(
        "/api/v1/shared/me",
        json={
            "email": "new_address@example.com",
            "current_password": "StrongPass1",
        },
        headers=headers,
    )

    assert res.status_code == 200
    assert res.json()["email"] == "old_email@example.com"
    assert res.json()["has_pending_email"] is True
    assert res.json()["verification_required"] is True


@pytest.mark.asyncio
async def test_update_me_email_duplicate(client: AsyncClient):
    """test_update_me_email_duplicate senaryosunu test eder."""
    await _auth_headers(client, "taken@example.com")
    headers = await _auth_headers(client, "wants_taken@example.com")

    res = await client.patch(
        "/api/v1/shared/me",
        json={"email": "taken@example.com", "current_password": "StrongPass1"},
        headers=headers,
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_update_me_email_requires_current_password(client: AsyncClient):
    """Email değişikliğinde current_password zorunlu olmalı."""
    headers = await _auth_headers(client, "missing_pw@example.com")
    res = await client.patch(
        "/api/v1/shared/me",
        json={"email": "new_missing_pw@example.com"},
        headers=headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_update_me_email_verification_promotes_pending_email(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_enqueue,
):
    """Verify token sonrası pending_email aktif email olmalı."""
    headers = await _auth_headers(client, "verify_me_old@example.com")
    mock_enqueue.reset_mock()

    res = await client.patch(
        "/api/v1/shared/me",
        json={
            "email": "verify_me_new@example.com",
            "current_password": "StrongPass1",
        },
        headers=headers,
    )
    assert res.status_code == 200

    token = mock_enqueue.call_args.args[2]
    verify_res = await client.post("/api/v1/client/auth/verify-email", json={"token": token})
    assert verify_res.status_code == 200

    user = await db_session.scalar(select(User).where(User.email == "verify_me_new@example.com"))
    assert user is not None
    assert user.pending_email is None
    assert user.is_verified is True


@pytest.mark.asyncio
async def test_update_me_password(client: AsyncClient):
    """test_update_me_password senaryosunu test eder."""
    email = "change_pw@example.com"
    headers = await _auth_headers(client, email)

    res = await client.patch("/api/v1/shared/me", json={"password": "NewPass123"}, headers=headers)
    assert res.status_code == 200

    # Yeni şifre çalışmalı
    login = await client.post(
        "/api/v1/client/auth/login", json={"email": email, "password": "NewPass123"}
    )
    assert login.status_code == 200

    # Eski şifre artık çalışmamalı
    old_login = await client.post(
        "/api/v1/client/auth/login", json={"email": email, "password": "StrongPass1"}
    )
    assert old_login.status_code == 401


@pytest.mark.asyncio
async def test_update_me_unauthorized(client: AsyncClient):
    """test_update_me_unauthorized senaryosunu test eder."""
    res = await client.patch("/api/v1/shared/me", json={"full_name": "Foo"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_update_me_no_fields_returns_current_user(client: AsyncClient):
    """Hiçbir alan gönderilmezse mevcut kullanıcı döner — 200."""
    headers = await _auth_headers(client, "noop_update@example.com")
    res = await client.patch("/api/v1/shared/me", json={}, headers=headers)

    assert res.status_code == 200
    assert res.json()["email"] == "noop_update@example.com"


# ── GET /users (Admin only) ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_users_as_admin(client: AsyncClient, db_session: AsyncSession):
    """test_list_users_as_admin senaryosunu test eder."""
    email = "admin_list@example.com"
    headers = await _auth_headers(client, email)
    await _promote_to_admin(db_session, email)

    res = await client.get("/api/v1/admin/users", headers=headers)

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
    res = await client.get("/api/v1/admin/users", headers=headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_list_users_unauthorized(client: AsyncClient):
    """test_list_users_unauthorized senaryosunu test eder."""
    res = await client.get("/api/v1/admin/users")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_list_users_pagination(client: AsyncClient, db_session: AsyncSession):
    """test_list_users_pagination senaryosunu test eder."""
    admin_email = "admin_pager@example.com"
    await _auth_headers(client, "pager_u1@example.com")
    await _auth_headers(client, "pager_u2@example.com")
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.get("/api/v1/admin/users?page=1&size=2", headers=headers)

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

    res = await client.get("/api/v1/admin/users", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["page"] == 1
    assert data["size"] == 20


# ── POST /users (Admin invite) ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_admin_user_as_authorized_admin(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_enqueue,
):
    """Yetkili admin yeni admin kullanıcı oluşturabilmeli."""
    creator_email = "admin_creator@example.com"
    headers = await _auth_headers(client, creator_email)
    await _promote_to_admin(db_session, creator_email)

    mock_enqueue.reset_mock()
    res = await client.post(
        "/api/v1/admin/users",
        json={
            "email": "new_admin@example.com",
            "role_name": "admin",
            "full_name": "New Admin",
            "username": "new_admin",
        },
        headers=headers,
    )

    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "new_admin@example.com"
    assert data["surface"] == SurfaceType.ADMIN.value
    assert data["is_verified"] is False
    mock_enqueue.assert_called_once()

    created = await db_session.execute(select(User).where(User.email == "new_admin@example.com"))
    user = created.scalar_one()
    assert user.hashed_password is None
    assert user.surface == SurfaceType.ADMIN.value


@pytest.mark.asyncio
async def test_create_admin_user_rejects_duplicate_email(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Aynı email ile admin kullanıcı oluşturma 409 dönmeli."""
    creator_email = "admin_creator_dup@example.com"
    headers = await _auth_headers(client, creator_email)
    await _promote_to_admin(db_session, creator_email)
    await _auth_headers(client, "dup_admin@example.com")

    res = await client.post(
        "/api/v1/admin/users",
        json={"email": "dup_admin@example.com", "role_name": "admin"},
        headers=headers,
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_create_admin_user_requires_create_permission(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Create_admin yetkisi olmayan admin surface kullanıcı admin create edememeli."""
    email = "moderator_admin@example.com"
    headers = await _auth_headers(client, email)

    result = await db_session.execute(select(Role.id).where(Role.name == "moderator"))
    moderator_role_id = result.scalar_one()
    await db_session.execute(
        sa_update(User)
        .where(User.email == email)
        .values(role_id=moderator_role_id, surface=SurfaceType.ADMIN.value)
    )
    await db_session.commit()
    db_session.expire_all()

    res = await client.post(
        "/api/v1/admin/users",
        json={"email": "blocked_admin@example.com", "role_name": "admin"},
        headers=headers,
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_create_admin_user_rejects_role_without_panel_access(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Panel erişimi olmayan role admin kullanıcı atanamamalı."""
    creator_email = "admin_creator_role@example.com"
    headers = await _auth_headers(client, creator_email)
    await _promote_to_admin(db_session, creator_email)

    res = await client.post(
        "/api/v1/admin/users",
        json={"email": "bad_role_admin@example.com", "role_name": "user"},
        headers=headers,
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_create_admin_user_accepts_custom_panel_role(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """admin:panel_access taşıyan özel rol ile admin kullanıcı oluşturulabilmeli."""
    creator_email = "admin_creator_custom_role@example.com"
    headers = await _auth_headers(client, creator_email)
    await _promote_to_admin(db_session, creator_email)

    custom_role = Role(name="support_admin", description="Support", is_system=False)
    db_session.add(custom_role)
    await db_session.flush()
    db_session.add(
        RolePermission(role_id=custom_role.id, permission=Permission.ADMIN_PANEL_ACCESS.value)
    )
    await db_session.commit()

    res = await client.post(
        "/api/v1/admin/users",
        json={"email": "support_admin_user@example.com", "role_name": "support_admin"},
        headers=headers,
    )
    assert res.status_code == 201
    assert res.json()["role"]["name"] == "support_admin"


@pytest.mark.asyncio
async def test_invited_admin_cannot_login_before_setting_password(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Davet edilen admin şifre belirlemeden admin login yapamamalı."""
    creator_email = "admin_creator_login@example.com"
    headers = await _auth_headers(client, creator_email)
    await _promote_to_admin(db_session, creator_email)

    create_res = await client.post(
        "/api/v1/admin/users",
        json={"email": "pending_admin@example.com", "role_name": "admin"},
        headers=headers,
    )
    assert create_res.status_code == 201

    login_res = await client.post(
        "/api/v1/admin/auth/login",
        json={"email": "pending_admin@example.com", "password": "StrongPass1"},
    )
    assert login_res.status_code == 401


@pytest.mark.asyncio
async def test_resend_admin_invite_for_pending_admin(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_enqueue,
):
    """Şifresi olmayan admin kullanıcı için davet yeniden gönderilebilmeli."""
    creator_email = "admin_creator_resend@example.com"
    headers = await _auth_headers(client, creator_email)
    await _promote_to_admin(db_session, creator_email)

    support_role = Role(name="resend_support_admin", description="Support", is_system=False)
    db_session.add(support_role)
    await db_session.flush()
    db_session.add(
        RolePermission(role_id=support_role.id, permission=Permission.ADMIN_PANEL_ACCESS.value)
    )
    await db_session.commit()

    create_res = await client.post(
        "/api/v1/admin/users",
        json={"email": "resend_admin@example.com", "role_name": "resend_support_admin"},
        headers=headers,
    )
    user_id = create_res.json()["id"]
    mock_enqueue.reset_mock()

    resend_res = await client.post(f"/api/v1/admin/users/{user_id}/resend-invite", headers=headers)
    assert resend_res.status_code == 200
    mock_enqueue.assert_called_once()


@pytest.mark.asyncio
async def test_resend_admin_invite_rejects_user_with_password(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_enqueue,
):
    """Şifresi belirlenmiş admin kullanıcı için resend başarısız olmalı."""
    creator_email = "admin_creator_resend_done@example.com"
    headers = await _auth_headers(client, creator_email)
    await _promote_to_admin(db_session, creator_email)

    support_role = Role(name="resend_done_support_admin", description="Support", is_system=False)
    db_session.add(support_role)
    await db_session.flush()
    db_session.add(
        RolePermission(role_id=support_role.id, permission=Permission.ADMIN_PANEL_ACCESS.value)
    )
    await db_session.commit()

    create_res = await client.post(
        "/api/v1/admin/users",
        json={"email": "resend_done_admin@example.com", "role_name": "resend_done_support_admin"},
        headers=headers,
    )
    user_id = create_res.json()["id"]
    token = mock_enqueue.call_args.args[2]
    await client.post(
        "/api/v1/shared/auth/reset-password",
        json={"token": token, "new_password": "NewStrongPass2"},
    )
    mock_enqueue.reset_mock()

    resend_res = await client.post(f"/api/v1/admin/users/{user_id}/resend-invite", headers=headers)
    assert resend_res.status_code == 400


# ── GET /users/{id} (Admin only) ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_user_by_id_as_admin(client: AsyncClient, db_session: AsyncSession):
    """test_get_user_by_id_as_admin senaryosunu test eder."""
    admin_email = "admin_getid@example.com"
    target_email = "target_getid@example.com"

    # Hedef kullanıcının ID'sini al
    target_headers = await _auth_headers(client, target_email)
    target_me = await client.get("/api/v1/shared/me", headers=target_headers)
    target_id = target_me.json()["id"]

    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.get(f"/api/v1/admin/users/{target_id}", headers=headers)

    assert res.status_code == 200
    assert res.json()["email"] == target_email


@pytest.mark.asyncio
async def test_get_user_by_id_as_non_admin(client: AsyncClient):
    """test_get_user_by_id_as_non_admin senaryosunu test eder."""
    target_headers = await _auth_headers(client, "target_perm@example.com")
    target_me = await client.get("/api/v1/shared/me", headers=target_headers)
    target_id = target_me.json()["id"]

    non_admin_headers = await _auth_headers(client, "non_admin_perm@example.com")
    res = await client.get(f"/api/v1/admin/users/{target_id}", headers=non_admin_headers)

    assert res.status_code == 403


@pytest.mark.asyncio
async def test_get_user_by_id_unauthorized(client: AsyncClient):
    """test_get_user_by_id_unauthorized senaryosunu test eder."""
    res = await client.get("/api/v1/admin/users/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_user_by_id_not_found(client: AsyncClient, db_session: AsyncSession):
    """test_get_user_by_id_not_found senaryosunu test eder."""
    admin_email = "admin_notfound@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    fake_id = "00000000-0000-0000-0000-000000000000"
    res = await client.get(f"/api/v1/admin/users/{fake_id}", headers=headers)

    assert res.status_code == 404


# ── PATCH /users/{id} & email management (Admin only) ───────────────────────


@pytest.mark.asyncio
async def test_admin_update_user_profile_fields(client: AsyncClient, db_session: AsyncSession):
    """Yetkili admin başka kullanıcının profil alanlarını güncelleyebilmeli."""
    actor_email = "profile_manager@example.com"
    target_email = "profile_target@example.com"
    target_headers = await _auth_headers(client, target_email)
    target_id = (await client.get("/api/v1/shared/me", headers=target_headers)).json()["id"]

    headers = await _auth_headers(client, actor_email)
    await _promote_to_admin_surface_role(
        db_session,
        email=actor_email,
        role_name="user_manager",
        permissions=[Permission.ADMIN_PANEL_ACCESS, Permission.USERS_WRITE],
    )

    res = await client.patch(
        f"/api/v1/admin/users/{target_id}",
        json={"full_name": "Managed User", "username": "managed_user"},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["full_name"] == "Managed User"
    assert res.json()["username"] == "managed_user"


@pytest.mark.asyncio
async def test_admin_change_user_email_sends_verification(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_enqueue,
):
    """Yetkili admin hedef kullanıcının e-posta değişikliğini başlatabilmeli."""
    actor_email = "email_manager@example.com"
    target_email = "email_target@example.com"
    target_headers = await _auth_headers(client, target_email)
    target_id = (await client.get("/api/v1/shared/me", headers=target_headers)).json()["id"]

    headers = await _auth_headers(client, actor_email)
    await _promote_to_admin_surface_role(
        db_session,
        email=actor_email,
        role_name="email_manager_role",
        permissions=[Permission.ADMIN_PANEL_ACCESS, Permission.USERS_CHANGE_EMAIL],
    )
    mock_enqueue.reset_mock()

    res = await client.post(
        f"/api/v1/admin/users/{target_id}/change-email",
        json={"email": "email_target_new@example.com"},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["email"] == target_email
    assert res.json()["has_pending_email"] is True

    user = await db_session.scalar(select(User).where(User.id == target_id))
    assert user is not None
    assert user.pending_email == "email_target_new@example.com"
    assert user.is_verified is False
    mock_enqueue.assert_called_once()


@pytest.mark.asyncio
async def test_admin_change_user_email_requires_permission(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """users:change_email yetkisi olmayan admin surface kullanıcı email değiştirememeli."""
    actor_email = "email_manager_blocked@example.com"
    target_email = "email_target_blocked@example.com"
    target_headers = await _auth_headers(client, target_email)
    target_id = (await client.get("/api/v1/shared/me", headers=target_headers)).json()["id"]

    headers = await _auth_headers(client, actor_email)
    await _promote_to_admin_surface_role(
        db_session,
        email=actor_email,
        role_name="write_only_manager",
        permissions=[Permission.ADMIN_PANEL_ACCESS, Permission.USERS_WRITE],
    )

    res = await client.post(
        f"/api/v1/admin/users/{target_id}/change-email",
        json={"email": "blocked_new@example.com"},
        headers=headers,
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_resend_user_verification_for_pending_email(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_enqueue,
):
    """Admin pending email bekleyen kullanıcı için verify mailini yeniden gönderebilmeli."""
    actor_email = "verify_resend_manager@example.com"
    target_email = "verify_resend_target@example.com"
    target_headers = await _auth_headers(client, target_email)
    target_id = (await client.get("/api/v1/shared/me", headers=target_headers)).json()["id"]

    self_headers = await _auth_headers(client, actor_email)
    await _promote_to_admin_surface_role(
        db_session,
        email=actor_email,
        role_name="verify_resend_role",
        permissions=[
            Permission.ADMIN_PANEL_ACCESS,
            Permission.USERS_CHANGE_EMAIL,
            Permission.USERS_RESEND_VERIFICATION,
        ],
    )

    await client.post(
        f"/api/v1/admin/users/{target_id}/change-email",
        json={"email": "verify_resend_target_new@example.com"},
        headers=self_headers,
    )
    mock_enqueue.reset_mock()

    res = await client.post(
        f"/api/v1/admin/users/{target_id}/resend-verification", headers=self_headers
    )
    assert res.status_code == 200
    mock_enqueue.assert_called_once()


@pytest.mark.asyncio
async def test_admin_user_management_blocks_admin_role_target(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_audit_log,
):
    """role=admin hedef kullanıcılar user-management ile değiştirilememeli."""
    actor_email = "non_admin_manager@example.com"
    target_email = "protected_admin_target@example.com"

    headers = await _auth_headers(client, actor_email)
    await _promote_to_admin_surface_role(
        db_session,
        email=actor_email,
        role_name="full_user_manager",
        permissions=[
            Permission.ADMIN_PANEL_ACCESS,
            Permission.USERS_WRITE,
            Permission.USERS_CHANGE_EMAIL,
            Permission.USERS_RESEND_VERIFICATION,
            Permission.USERS_DELETE,
            Permission.USERS_READ,
        ],
    )

    target_headers = await _auth_headers(client, target_email)
    target_id = (await client.get("/api/v1/shared/me", headers=target_headers)).json()["id"]
    await _promote_to_admin(db_session, target_email)
    mock_audit_log.reset_mock()

    res = await client.post(
        f"/api/v1/admin/users/{target_id}/change-email",
        json={"email": "blocked_admin_target_new@example.com"},
        headers=headers,
    )
    assert res.status_code == 403
    assert any(
        call.args[0] == AuditAction.USER_MANAGEMENT_BLOCKED
        and call.kwargs["extra"]["reason"] == "protected_admin_role"
        for call in mock_audit_log.call_args_list
    )


# ── DELETE /users/{id} (Admin only) ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_deactivate_user_as_admin(client: AsyncClient, db_session: AsyncSession):
    """test_deactivate_user_as_admin senaryosunu test eder."""
    admin_email = "admin_deact@example.com"
    target_email = "target_deact@example.com"

    target_headers = await _auth_headers(client, target_email)
    target_me = await client.get("/api/v1/shared/me", headers=target_headers)
    target_id = target_me.json()["id"]

    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.delete(
        f"/api/v1/admin/users/{target_id}",
        headers={**headers, "Accept-Language": "tr"},
    )
    assert res.status_code == 200
    assert "silindi" in res.json()["message"]

    # Soft-deleted kullanıcı artık giriş yapamamalı
    login = await client.post(
        "/api/v1/client/auth/login", json={"email": target_email, "password": "StrongPass1"}
    )
    assert login.status_code == 401


@pytest.mark.asyncio
async def test_deactivate_user_as_non_admin(client: AsyncClient):
    """test_deactivate_user_as_non_admin senaryosunu test eder."""
    target_headers = await _auth_headers(client, "target_nodeact@example.com")
    target_me = await client.get("/api/v1/shared/me", headers=target_headers)
    target_id = target_me.json()["id"]

    non_admin_headers = await _auth_headers(client, "non_admin_nodeact@example.com")
    res = await client.delete(f"/api/v1/admin/users/{target_id}", headers=non_admin_headers)

    assert res.status_code == 403


@pytest.mark.asyncio
async def test_deactivate_user_unauthorized(client: AsyncClient):
    """test_deactivate_user_unauthorized senaryosunu test eder."""
    res = await client.delete("/api/v1/admin/users/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_deactivate_nonexistent_user(client: AsyncClient, db_session: AsyncSession):
    """Admin ile var olmayan UUID → 404."""
    admin_email = "admin_404del@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    fake_id = "00000000-0000-0000-0000-000000000001"
    res = await client.delete(f"/api/v1/admin/users/{fake_id}", headers=headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_update_me_password_too_short(client: AsyncClient):
    """8 karakterden kısa şifre ile PATCH /users/me → 422."""
    headers = await _auth_headers(client, "shortpw_update@example.com")
    res = await client.patch("/api/v1/shared/me", json={"password": "Sh0rt"}, headers=headers)
    assert res.status_code == 422


# ── GET /users?q= (Arama) ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_users_search_by_email(client: AsyncClient, db_session: AsyncSession):
    """q parametresi ile email araması çalışmalı."""
    admin_email = "admin_srch_email@example.com"
    await _auth_headers(client, "unique_srch_target@example.com")
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.get("/api/v1/admin/users?q=unique_srch_target", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert any("unique_srch_target" in u["email"] for u in data["items"])


@pytest.mark.asyncio
async def test_list_users_search_by_username(client: AsyncClient, db_session: AsyncSession):
    """q parametresi ile username araması çalışmalı."""
    admin_email = "admin_srch_uname@example.com"
    target_headers = await _auth_headers(client, "srch_uname_user@example.com")
    await client.patch(
        "/api/v1/shared/me", json={"username": "findme_username"}, headers=target_headers
    )
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.get("/api/v1/admin/users?q=findme_username", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert any(u.get("username") == "findme_username" for u in data["items"])


@pytest.mark.asyncio
async def test_list_users_search_no_match(client: AsyncClient, db_session: AsyncSession):
    """Eşleşmeyen q parametresi → boş liste, total=0."""
    admin_email = "admin_srch_empty@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.get("/api/v1/admin/users?q=zzznomatchzzz99999", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_users_search_whitespace_only_ignored(
    client: AsyncClient, db_session: AsyncSession
):
    """Sadece boşluktan oluşan q parametresi arama yapmadan tüm kullanıcıları döndürmeli."""
    admin_email = "admin_srch_ws@example.com"
    await _auth_headers(client, "ws_srch_user@example.com")
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res_all = await client.get("/api/v1/admin/users", headers=headers)
    res_ws = await client.get("/api/v1/admin/users?q=   ", headers=headers)

    # Boşluk-only q → strip() → None → tüm kullanıcılar döner (filtre uygulanmaz)
    assert res_ws.status_code == 200
    assert res_ws.json()["total"] == res_all.json()["total"]


# ── GET /users?role= (Rol Filtresi) ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_users_filter_by_role(client: AsyncClient, db_session: AsyncSession):
    """role parametresi ile filtreleme çalışmalı."""
    admin_email = "admin_role_filter@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.get("/api/v1/admin/users?role=user", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert all(u["role"]["name"] == "user" for u in data["items"])


@pytest.mark.asyncio
async def test_list_users_filter_by_admin_role(client: AsyncClient, db_session: AsyncSession):
    """role=admin filtresi ile yalnızca admin kullanıcılar gelmeli."""
    admin_email = "admin_role_admin_filter@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.get("/api/v1/admin/users?role=admin", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert all(u["role"]["name"] == "admin" for u in data["items"])


# ── GET /users?is_active= (Aktiflik Filtresi) ────────────────────────────────


@pytest.mark.asyncio
async def test_list_users_filter_is_active_false(client: AsyncClient, db_session: AsyncSession):
    """is_active=false filtresi ile yalnızca pasif kullanıcılar gelmeli."""
    admin_email = "admin_act_filter@example.com"
    target_email = "deact_filter_target@example.com"

    target_headers = await _auth_headers(client, target_email)
    target_id = (await client.get("/api/v1/shared/me", headers=target_headers)).json()["id"]

    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    # Kullanıcıyı deaktif et
    await client.post(f"/api/v1/admin/users/{target_id}/deactivate", headers=headers)

    res = await client.get("/api/v1/admin/users?is_active=false", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert all(u["is_active"] is False for u in data["items"])


@pytest.mark.asyncio
async def test_list_users_filter_is_active_true(client: AsyncClient, db_session: AsyncSession):
    """is_active=true filtresi ile yalnızca aktif kullanıcılar gelmeli."""
    admin_email = "admin_active_true@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.get("/api/v1/admin/users?is_active=true", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert all(u["is_active"] is True for u in data["items"])


# ── GET /users?is_verified= (Doğrulama Filtresi) ─────────────────────────────


@pytest.mark.asyncio
async def test_list_users_filter_is_verified_false(client: AsyncClient, db_session: AsyncSession):
    """is_verified=false filtresi ile yalnızca doğrulanmamış kullanıcılar gelmeli."""
    admin_email = "admin_unverif@example.com"
    await _auth_headers(client, "unverif_user@example.com")
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.get("/api/v1/admin/users?is_verified=false", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert all(u["is_verified"] is False for u in data["items"])


# ── Kombinasyon Filtreleri ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_users_combined_filters(client: AsyncClient, db_session: AsyncSession):
    """q + role + is_active kombinasyonu çalışmalı."""
    admin_email = "admin_combo@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.get(
        "/api/v1/admin/users?role=user&is_active=true&is_verified=false", headers=headers
    )

    assert res.status_code == 200
    data = res.json()
    for u in data["items"]:
        assert u["role"]["name"] == "user"
        assert u["is_active"] is True
        assert u["is_verified"] is False


# ── GET /users/stats ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_user_stats_as_admin(client: AsyncClient, db_session: AsyncSession):
    """Admin kullanıcı istatistiklerini görebilmeli."""
    admin_email = "admin_stats@example.com"
    await _auth_headers(client, "stats_user1@example.com")
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.get("/api/v1/admin/users/stats", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "active" in data
    assert "inactive" in data
    assert data["total"] >= 2


@pytest.mark.asyncio
async def test_get_user_stats_as_non_admin(client: AsyncClient):
    """Non-admin kullanıcı istatistiklerine erişememeli."""
    headers = await _auth_headers(client, "non_admin_stats@example.com")
    res = await client.get("/api/v1/admin/users/stats", headers=headers)
    assert res.status_code == 403


# ── POST /users/{id}/activate & POST /users/{id}/deactivate ──────────────────


@pytest.mark.asyncio
async def test_deactivate_and_activate_user(client: AsyncClient, db_session: AsyncSession):
    """Admin kullanıcıyı deaktif edip tekrar aktif edebilmeli."""
    admin_email = "admin_actdeact@example.com"
    target_email = "actdeact_target@example.com"

    target_headers = await _auth_headers(client, target_email)
    target_id = (await client.get("/api/v1/shared/me", headers=target_headers)).json()["id"]

    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    # Deaktif et
    res = await client.post(f"/api/v1/admin/users/{target_id}/deactivate", headers=headers)
    assert res.status_code == 200
    assert res.json()["is_active"] is False

    # Tekrar aktif et
    res = await client.post(f"/api/v1/admin/users/{target_id}/activate", headers=headers)
    assert res.status_code == 200
    assert res.json()["is_active"] is True


@pytest.mark.asyncio
async def test_admin_cannot_deactivate_self(client: AsyncClient, db_session: AsyncSession):
    """Admin kendi hesabını deaktif edemez."""
    admin_email = "admin_self_deact@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    me = await client.get("/api/v1/shared/me", headers=headers)
    admin_id = me.json()["id"]

    res = await client.post(f"/api/v1/admin/users/{admin_id}/deactivate", headers=headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_activate_self(client: AsyncClient, db_session: AsyncSession):
    """Admin kendi hesabını aktif edemez."""
    admin_email = "admin_self_act@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    me = await client.get("/api/v1/shared/me", headers=headers)
    admin_id = me.json()["id"]

    res = await client.post(f"/api/v1/admin/users/{admin_id}/activate", headers=headers)
    assert res.status_code == 403


# ── PATCH /users/{id}/role ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_assign_role_as_admin(client: AsyncClient, db_session: AsyncSession):
    """Admin başka bir kullanıcıya rol atayabilmeli."""
    admin_email = "admin_assign_role@example.com"
    target_email = "role_assign_target@example.com"

    target_headers = await _auth_headers(client, target_email)
    target_id = (await client.get("/api/v1/shared/me", headers=target_headers)).json()["id"]

    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.patch(
        f"/api/v1/admin/users/{target_id}/role",
        json={"role_name": "moderator"},
        headers=headers,
    )

    assert res.status_code == 200
    assert res.json()["role"]["name"] == "moderator"


@pytest.mark.asyncio
async def test_assign_nonexistent_role(client: AsyncClient, db_session: AsyncSession):
    """Var olmayan rol adı → 404."""
    admin_email = "admin_bad_role@example.com"
    target_email = "bad_role_target@example.com"

    target_headers = await _auth_headers(client, target_email)
    target_id = (await client.get("/api/v1/shared/me", headers=target_headers)).json()["id"]

    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.patch(
        f"/api/v1/admin/users/{target_id}/role",
        json={"role_name": "nonexistent_role"},
        headers=headers,
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_admin_cannot_change_own_role(client: AsyncClient, db_session: AsyncSession):
    """Admin kendi rolünü değiştiremez."""
    admin_email = "admin_self_role@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    me = await client.get("/api/v1/shared/me", headers=headers)
    admin_id = me.json()["id"]

    res = await client.patch(
        f"/api/v1/admin/users/{admin_id}/role",
        json={"role_name": "user"},
        headers=headers,
    )
    assert res.status_code == 403


# ── GET /users/deleted & POST /users/{id}/restore ────────────────────────────


@pytest.mark.asyncio
async def test_list_deleted_users(client: AsyncClient, db_session: AsyncSession):
    """Soft-delete ile silinen kullanıcılar /users/deleted listesinde görünmeli."""
    admin_email = "admin_deleted_list@example.com"
    target_email = "deleted_list_target@example.com"

    target_headers = await _auth_headers(client, target_email)
    target_id = (await client.get("/api/v1/shared/me", headers=target_headers)).json()["id"]

    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    # Soft-delete
    await client.delete(f"/api/v1/admin/users/{target_id}", headers=headers)

    res = await client.get("/api/v1/admin/users/deleted", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert any(u["id"] == target_id for u in data["items"])
    assert all(u["deleted_at"] is not None for u in data["items"])


@pytest.mark.asyncio
async def test_list_deleted_users_as_non_admin(client: AsyncClient):
    """Non-admin silinen kullanıcı listesine erişememeli."""
    headers = await _auth_headers(client, "non_admin_deleted@example.com")
    res = await client.get("/api/v1/admin/users/deleted", headers=headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_list_deleted_users_search(client: AsyncClient, db_session: AsyncSession):
    """Silinen kullanıcılar listesinde q parametresi çalışmalı."""
    admin_email = "admin_del_srch@example.com"
    target_email = "del_srch_unique99@example.com"

    target_headers = await _auth_headers(client, target_email)
    target_id = (await client.get("/api/v1/shared/me", headers=target_headers)).json()["id"]

    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    await client.delete(f"/api/v1/admin/users/{target_id}", headers=headers)

    res = await client.get("/api/v1/admin/users/deleted?q=del_srch_unique99", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert any("del_srch_unique99" in u["email"] for u in data["items"])


@pytest.mark.asyncio
async def test_restore_deleted_user(client: AsyncClient, db_session: AsyncSession):
    """Soft-delete ile silinen kullanıcı restore edilebilmeli."""
    admin_email = "admin_restore@example.com"
    target_email = "restore_target@example.com"

    target_headers = await _auth_headers(client, target_email)
    target_id = (await client.get("/api/v1/shared/me", headers=target_headers)).json()["id"]

    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    # Soft-delete
    await client.delete(f"/api/v1/admin/users/{target_id}", headers=headers)

    # Restore
    res = await client.post(f"/api/v1/admin/users/{target_id}/restore", headers=headers)
    assert res.status_code == 200
    assert res.json()["id"] == target_id

    # Artık aktif listede görünmeli
    res_list = await client.get(f"/api/v1/admin/users/{target_id}", headers=headers)
    assert res_list.status_code == 200


@pytest.mark.asyncio
async def test_restore_nondeleted_user_fails(client: AsyncClient, db_session: AsyncSession):
    """Silinmemiş kullanıcıyı restore etmeye çalışmak → 409/4xx."""
    admin_email = "admin_restore_err@example.com"
    target_email = "restore_err_target@example.com"

    target_headers = await _auth_headers(client, target_email)
    target_id = (await client.get("/api/v1/shared/me", headers=target_headers)).json()["id"]

    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    res = await client.post(f"/api/v1/admin/users/{target_id}/restore", headers=headers)
    assert res.status_code in (409, 400)


@pytest.mark.asyncio
async def test_admin_cannot_delete_self(client: AsyncClient, db_session: AsyncSession):
    """Admin kendi hesabını soft-delete ile silemez."""
    admin_email = "admin_self_del@example.com"
    headers = await _auth_headers(client, admin_email)
    await _promote_to_admin(db_session, admin_email)

    me = await client.get("/api/v1/shared/me", headers=headers)
    admin_id = me.json()["id"]

    res = await client.delete(f"/api/v1/admin/users/{admin_id}", headers=headers)
    assert res.status_code == 403
