"""Auth endpoint testleri."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select
from sqlalchemy import update as sa_update

from app.core.system_roles import PANEL_ADMIN_ROLE
from app.db.models.api_key import APIKey
from app.db.models.role import Role
from app.db.models.user import SurfaceType, User
from app.services._keys import LOGIN_PARTIAL_KEY
from app.tasks.worker import send_admin_password_reset_email, send_password_reset_email

if TYPE_CHECKING:
    from unittest.mock import AsyncMock

    import fakeredis.aioredis as fakeredis_aioredis
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """test_register_success senaryosunu test eder."""
    res = await client.post(
        "/api/v1/client/auth/register",
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
    """test_register_duplicate_email senaryosunu test eder."""
    payload = {"email": "dup@example.com", "password": "StrongPass1"}
    await client.post("/api/v1/client/auth/register", json=payload)
    res = await client.post("/api/v1/client/auth/register", json=payload)
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """test_login_success senaryosunu test eder."""
    await client.post(
        "/api/v1/client/auth/register",
        json={
            "email": "login@example.com",
            "password": "StrongPass1",
        },
    )
    res = await client.post(
        "/api/v1/client/auth/login",
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
async def test_login_sets_cookies(client: AsyncClient):
    """Login başarılı olduğunda httpOnly cookie'ler set edilmeli."""
    await client.post(
        "/api/v1/client/auth/register",
        json={
            "email": "cookie_login@example.com",
            "password": "StrongPass1",
        },
    )
    res = await client.post(
        "/api/v1/client/auth/login",
        json={
            "email": "cookie_login@example.com",
            "password": "StrongPass1",
        },
    )
    assert res.status_code == 200

    # Cookie'lerin set edildiğini kontrol et
    cookies = res.cookies
    assert "access_token" in cookies
    assert "refresh_token" in cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """test_login_wrong_password senaryosunu test eder."""
    res = await client.post(
        "/api/v1/client/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "WrongPass1",
        },
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_admin_user_cannot_use_client_login(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Admin surface kullanıcı client login yüzeyinden token alamamalı."""
    email = "admin_surface_block@example.com"
    password = "StrongPass1"

    await client.post(
        "/api/v1/client/auth/register",
        json={"email": email, "password": password},
    )

    result = await db_session.execute(select(Role.id).where(Role.name == PANEL_ADMIN_ROLE))
    admin_role_id = result.scalar_one()
    await db_session.execute(
        sa_update(User)
        .where(User.email == email)
        .values(role_id=admin_role_id, surface=SurfaceType.ADMIN.value)
    )
    await db_session.commit()

    res = await client.post(
        "/api/v1/client/auth/login",
        json={"email": email, "password": password},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_admin_user_can_use_admin_login(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Admin surface kullanıcı admin login yüzeyinden token alabilmeli."""
    email = "admin_surface_ok@example.com"
    password = "StrongPass1"

    await client.post(
        "/api/v1/client/auth/register",
        json={"email": email, "password": password},
    )

    result = await db_session.execute(select(Role.id).where(Role.name == PANEL_ADMIN_ROLE))
    admin_role_id = result.scalar_one()
    await db_session.execute(
        sa_update(User)
        .where(User.email == email)
        .values(role_id=admin_role_id, surface=SurfaceType.ADMIN.value)
    )
    await db_session.commit()

    res = await client.post(
        "/api/v1/admin/auth/login",
        json={"email": email, "password": password},
    )
    assert res.status_code == 200
    assert "access_token" in res.json()


@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient):
    # Register + login
    """test_get_me_authenticated senaryosunu test eder."""
    await client.post(
        "/api/v1/client/auth/register",
        json={
            "email": "me@example.com",
            "password": "StrongPass1",
        },
    )
    login = await client.post(
        "/api/v1/client/auth/login",
        json={
            "email": "me@example.com",
            "password": "StrongPass1",
        },
    )
    token = login.json()["access_token"]

    res = await client.get("/api/v1/shared/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    """test_get_me_unauthorized senaryosunu test eder."""
    res = await client.get("/api/v1/shared/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """test_health_check senaryosunu test eder."""
    res = await client.get("/health")
    assert res.status_code == 200
    data = res.json()
    # Test ortamında storage bağlantısı olmayabilir — "ok" veya "degraded" kabul edilir
    assert data["status"] in ("ok", "degraded")
    assert "version" in data
    assert "env" in data


# ── Email Verification ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_email_success(
    client: AsyncClient,
    fake_redis: fakeredis_aioredis.FakeRedis,
    mock_enqueue: AsyncMock,
):
    """Kayıt sonrası oluşturulan token ile e-posta doğrulaması başarılı olmalı."""
    await client.post(
        "/api/v1/client/auth/register",
        json={
            "email": "verify@example.com",
            "password": "StrongPass1",
        },
    )
    # enqueue(send_verification_email, email, token) çağrısından token'ı al
    token = mock_enqueue.call_args.args[2]

    res = await client.post(
        "/api/v1/client/auth/verify-email",
        json={"token": token},
        headers={"Accept-Language": "tr"},
    )
    assert res.status_code == 200
    assert "doğrulandı" in res.json()["message"]

    # Token tek kullanımlık — Redis'ten silinmiş olmalı
    assert await fake_redis.get(f"email_verify:{token}") is None


@pytest.mark.asyncio
async def test_verify_email_invalid_token(client: AsyncClient):
    """Geçersiz token 401 döndürmeli."""
    res = await client.post("/api/v1/client/auth/verify-email", json={"token": "invalid-token-xyz"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_resend_verification(client: AsyncClient, mock_enqueue: AsyncMock):
    """Doğrulanmamış kullanıcı için yeniden e-posta gönderilmeli."""
    await client.post(
        "/api/v1/client/auth/register",
        json={
            "email": "resend@example.com",
            "password": "StrongPass1",
        },
    )
    mock_enqueue.reset_mock()

    res = await client.post(
        "/api/v1/client/auth/resend-verification", json={"email": "resend@example.com"}
    )
    assert res.status_code == 200
    mock_enqueue.assert_called_once()


@pytest.mark.asyncio
async def test_resend_verification_nonexistent_email(client: AsyncClient, mock_enqueue: AsyncMock):
    """Var olmayan e-posta için 200 dönmeli, e-posta gönderilmemeli (user enumeration yok)."""
    mock_enqueue.reset_mock()
    res = await client.post(
        "/api/v1/client/auth/resend-verification", json={"email": "ghost@example.com"}
    )
    assert res.status_code == 200
    mock_enqueue.assert_not_called()


# ── Password Reset ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_forgot_password_returns_200_always(client: AsyncClient, mock_enqueue: AsyncMock):
    """Var olmayan kullanıcı için de 200 dönmeli (user enumeration yok)."""
    mock_enqueue.reset_mock()
    res = await client.post(
        "/api/v1/shared/auth/forgot-password", json={"email": "nobody@example.com"}
    )
    assert res.status_code == 200
    mock_enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_forgot_password_existing_user(client: AsyncClient, mock_enqueue: AsyncMock):
    """Var olan kullanıcı için e-posta gönderme task'ı enqueue edilmeli."""
    await client.post(
        "/api/v1/client/auth/register",
        json={
            "email": "reset@example.com",
            "password": "StrongPass1",
        },
    )
    mock_enqueue.reset_mock()

    res = await client.post(
        "/api/v1/shared/auth/forgot-password", json={"email": "reset@example.com"}
    )
    assert res.status_code == 200
    mock_enqueue.assert_called_once()
    assert mock_enqueue.call_args.args[0] is send_password_reset_email


@pytest.mark.asyncio
async def test_forgot_password_existing_admin_uses_admin_email_task(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_enqueue: AsyncMock,
):
    """Admin hesap shared forgot-password ile admin reset maili almalı."""
    email = "admin_reset@example.com"
    await client.post(
        "/api/v1/client/auth/register", json={"email": email, "password": "StrongPass1"}
    )

    result = await db_session.execute(select(Role.id).where(Role.name == PANEL_ADMIN_ROLE))
    admin_role_id = result.scalar_one()
    await db_session.execute(
        sa_update(User)
        .where(User.email == email)
        .values(role_id=admin_role_id, surface=SurfaceType.ADMIN.value)
    )
    await db_session.commit()
    mock_enqueue.reset_mock()

    res = await client.post("/api/v1/shared/auth/forgot-password", json={"email": email})
    assert res.status_code == 200
    mock_enqueue.assert_called_once()
    assert mock_enqueue.call_args.args[0] is send_admin_password_reset_email


@pytest.mark.asyncio
async def test_reset_password_success(
    client: AsyncClient,
    fake_redis: fakeredis_aioredis.FakeRedis,
    mock_enqueue: AsyncMock,
):
    """Token ile şifre sıfırlandıktan sonra yeni şifre ile giriş yapılabilmeli."""
    await client.post(
        "/api/v1/client/auth/register",
        json={
            "email": "pwreset@example.com",
            "password": "StrongPass1",
        },
    )
    mock_enqueue.reset_mock()

    await client.post("/api/v1/shared/auth/forgot-password", json={"email": "pwreset@example.com"})
    token = mock_enqueue.call_args.args[2]

    res = await client.post(
        "/api/v1/shared/auth/reset-password",
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
        "/api/v1/client/auth/login",
        json={
            "email": "pwreset@example.com",
            "password": "NewStrongPass2",
        },
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_marks_invited_admin_verified(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_enqueue: AsyncMock,
):
    """Davet edilen admin kullanıcı şifre kurunca verified olmalı."""
    creator_email = "creator@example.com"
    headers = await _register_and_login(client, creator_email)

    result = await db_session.execute(select(Role.id).where(Role.name == PANEL_ADMIN_ROLE))
    admin_role_id = result.scalar_one()
    await db_session.execute(
        sa_update(User)
        .where(User.email == creator_email)
        .values(role_id=admin_role_id, surface=SurfaceType.ADMIN.value)
    )
    await db_session.commit()
    admin_headers = {"Authorization": f"Bearer {headers['access_token']}"}

    mock_enqueue.reset_mock()
    create_res = await client.post(
        "/api/v1/admin/users",
        json={"email": "invited_admin@example.com", "role_name": PANEL_ADMIN_ROLE},
        headers=admin_headers,
    )
    assert create_res.status_code == 201
    token = mock_enqueue.call_args.args[2]

    reset_res = await client.post(
        "/api/v1/shared/auth/reset-password",
        json={"token": token, "new_password": "NewStrongPass2"},
    )
    assert reset_res.status_code == 200

    invited = await db_session.execute(
        select(User).where(User.email == "invited_admin@example.com")
    )
    assert invited.scalar_one().is_verified is True


@pytest.mark.asyncio
async def test_shared_reset_accepts_admin_token(
    client: AsyncClient,
    db_session: AsyncSession,
    mock_enqueue: AsyncMock,
):
    """Admin token shared reset yüzeyinde kullanılabilmeli."""
    creator_email = "creator_surface@example.com"
    headers = await _register_and_login(client, creator_email)

    result = await db_session.execute(select(Role.id).where(Role.name == PANEL_ADMIN_ROLE))
    admin_role_id = result.scalar_one()
    await db_session.execute(
        sa_update(User)
        .where(User.email == creator_email)
        .values(role_id=admin_role_id, surface=SurfaceType.ADMIN.value)
    )
    await db_session.commit()
    admin_headers = {"Authorization": f"Bearer {headers['access_token']}"}

    mock_enqueue.reset_mock()
    create_res = await client.post(
        "/api/v1/admin/users",
        json={"email": "surface_admin@example.com", "role_name": PANEL_ADMIN_ROLE},
        headers=admin_headers,
    )
    assert create_res.status_code == 201
    token = mock_enqueue.call_args.args[2]

    res = await client.post(
        "/api/v1/shared/auth/reset-password",
        json={"token": token, "new_password": "NewStrongPass2"},
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_shared_reset_accepts_client_token(
    client: AsyncClient,
    mock_enqueue: AsyncMock,
):
    """Client token shared reset yüzeyinde kullanılabilmeli."""
    await client.post(
        "/api/v1/client/auth/register",
        json={"email": "surface_client@example.com", "password": "StrongPass1"},
    )
    mock_enqueue.reset_mock()
    await client.post(
        "/api/v1/shared/auth/forgot-password",
        json={"email": "surface_client@example.com"},
    )
    token = mock_enqueue.call_args.args[2]

    res = await client.post(
        "/api/v1/shared/auth/reset-password",
        json={"token": token, "new_password": "NewStrongPass2"},
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_invalid_token(client: AsyncClient):
    """Geçersiz token 401 döndürmeli."""
    res = await client.post(
        "/api/v1/shared/auth/reset-password",
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
        "/api/v1/client/auth/register",
        json={
            "email": "oneuse@example.com",
            "password": "StrongPass1",
        },
    )
    mock_enqueue.reset_mock()

    await client.post("/api/v1/shared/auth/forgot-password", json={"email": "oneuse@example.com"})
    token = mock_enqueue.call_args.args[2]

    await client.post(
        "/api/v1/shared/auth/reset-password",
        json={
            "token": token,
            "new_password": "NewStrongPass2",
        },
    )

    # İkinci kullanım başarısız olmalı
    res = await client.post(
        "/api/v1/shared/auth/reset-password",
        json={
            "token": token,
            "new_password": "AnotherPass3",
        },
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_client_reset_revokes_existing_sessions_and_api_keys(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: fakeredis_aioredis.FakeRedis,
    mock_enqueue: AsyncMock,
):
    """Client reset sonrası access/refresh/partial session ve API key'ler geçersiz olmalı."""
    email = "client_revoke@example.com"
    tokens = await _register_and_login(client, email)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    create_key = await client.post(
        "/api/v1/shared/api-keys",
        json={"name": "Primary Key"},
        headers=headers,
    )
    assert create_key.status_code == 201

    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    user_id = user.id
    partial_token = "partial-reset-client"
    await fake_redis.set(
        LOGIN_PARTIAL_KEY.format(partial_token),
        f"{user_id}|{user.created_at.isoformat()}",
    )

    mock_enqueue.reset_mock()
    await client.post("/api/v1/shared/auth/forgot-password", json={"email": email})
    token = mock_enqueue.call_args.args[2]

    reset_res = await client.post(
        "/api/v1/shared/auth/reset-password",
        json={"token": token, "new_password": "NewStrongPass2"},
    )
    assert reset_res.status_code == 200

    me_res = await client.get("/api/v1/shared/me", headers=headers)
    assert me_res.status_code == 401

    refresh_res = await client.post(
        "/api/v1/shared/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_res.status_code == 401

    partial_res = await client.post(
        "/api/v1/shared/auth/totp-challenge",
        json={"partial_token": partial_token, "code": "123456"},
    )
    assert partial_res.status_code == 401

    api_keys = (
        (await db_session.execute(select(APIKey).where(APIKey.user_id == user_id))).scalars().all()
    )
    assert api_keys
    assert all(api_key.is_active is False for api_key in api_keys)


@pytest.mark.asyncio
async def test_admin_reset_revokes_existing_sessions_and_api_keys(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_redis: fakeredis_aioredis.FakeRedis,
    mock_enqueue: AsyncMock,
):
    """Admin reset sonrası access/refresh/partial session ve API key'ler geçersiz olmalı."""
    email = "revoke_admin@example.com"
    password = "StrongPass1"
    await client.post("/api/v1/client/auth/register", json={"email": email, "password": password})

    result = await db_session.execute(select(Role.id).where(Role.name == PANEL_ADMIN_ROLE))
    admin_role_id = result.scalar_one()
    await db_session.execute(
        sa_update(User)
        .where(User.email == email)
        .values(role_id=admin_role_id, surface=SurfaceType.ADMIN.value)
    )
    await db_session.commit()

    login = await client.post(
        "/api/v1/admin/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    tokens = login.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    create_key = await client.post(
        "/api/v1/shared/api-keys",
        json={"name": "Admin Key"},
        headers=headers,
    )
    assert create_key.status_code == 201

    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    user_id = user.id
    partial_token = "partial-reset-admin"
    await fake_redis.set(
        LOGIN_PARTIAL_KEY.format(partial_token),
        f"{user_id}|{user.created_at.isoformat()}",
    )

    mock_enqueue.reset_mock()
    await client.post("/api/v1/shared/auth/forgot-password", json={"email": email})
    token = mock_enqueue.call_args.args[2]

    reset_res = await client.post(
        "/api/v1/shared/auth/reset-password",
        json={"token": token, "new_password": "NewStrongPass2"},
    )
    assert reset_res.status_code == 200

    users_res = await client.get("/api/v1/admin/users", headers=headers)
    assert users_res.status_code == 401

    refresh_res = await client.post(
        "/api/v1/shared/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_res.status_code == 401

    partial_res = await client.post(
        "/api/v1/shared/auth/totp-challenge",
        json={"partial_token": partial_token, "code": "123456"},
    )
    assert partial_res.status_code == 401

    api_keys = (
        (await db_session.execute(select(APIKey).where(APIKey.user_id == user_id))).scalars().all()
    )
    assert api_keys
    assert all(api_key.is_active is False for api_key in api_keys)


# ── Token Blacklist + Refresh Rotation ────────────────────────────────────────


async def _register_and_login(client: AsyncClient, email: str) -> dict:
    """Yardımcı: kayıt + giriş → token çifti döner."""
    await client.post(
        "/api/v1/client/auth/register",
        json={
            "email": email,
            "password": "StrongPass1",
        },
    )
    res = await client.post(
        "/api/v1/client/auth/login",
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
        "/api/v1/shared/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=headers,
    )

    res = await client.get("/api/v1/shared/me", headers=headers)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_logout_invalidates_refresh_token(client: AsyncClient):
    """Logout sonrası aynı refresh token ile /refresh çağrısı 401 dönmeli."""
    tokens = await _register_and_login(client, "logout_refresh@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    await client.post(
        "/api/v1/shared/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=headers,
    )

    res = await client.post(
        "/api/v1/shared/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_logout_clears_cookies(client: AsyncClient):
    """Logout response'unda cookie'ler temizlenmeli (max-age=0)."""
    tokens = await _register_and_login(client, "logout_cookie@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    res = await client.post(
        "/api/v1/shared/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=headers,
    )
    assert res.status_code == 200

    # Cookie'lerin silinmesi için Set-Cookie header'larını kontrol et
    # delete_cookie max-age=0 veya expires ile cookie'yi siler
    set_cookie_headers = res.headers.get_list("set-cookie")
    access_cookie_cleared = any(
        "access_token" in h and "Max-Age=0" in h for h in set_cookie_headers
    )
    refresh_cookie_cleared = any(
        "refresh_token" in h and "Max-Age=0" in h for h in set_cookie_headers
    )
    assert access_cookie_cleared, "access_token cookie should be cleared"
    assert refresh_cookie_cleared, "refresh_token cookie should be cleared"


@pytest.mark.asyncio
async def test_refresh_token_rotation(client: AsyncClient):
    """Refresh sonrası eski refresh token geçersiz kılınmalı (rotation)."""
    tokens = await _register_and_login(client, "rotation@example.com")
    old_refresh = tokens["refresh_token"]

    # İlk refresh — yeni token çifti alınır
    res = await client.post("/api/v1/shared/auth/refresh", json={"refresh_token": old_refresh})
    assert res.status_code == 200

    # Eski refresh token artık kullanılamamalı
    res = await client.post("/api/v1/shared/auth/refresh", json={"refresh_token": old_refresh})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_refresh_sets_cookies(client: AsyncClient):
    """Refresh başarılı olduğunda yeni cookie'ler set edilmeli."""
    tokens = await _register_and_login(client, "refresh_cookie@example.com")

    res = await client.post(
        "/api/v1/shared/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert res.status_code == 200

    # Cookie'lerin set edildiğini kontrol et
    cookies = res.cookies
    assert "access_token" in cookies
    assert "refresh_token" in cookies


@pytest.mark.asyncio
async def test_refresh_blacklisted_token(client: AsyncClient):
    """Logout ile blacklist'e alınan refresh token /refresh'te 401 dönmeli."""
    tokens = await _register_and_login(client, "blacklist_refresh@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    await client.post(
        "/api/v1/shared/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=headers,
    )

    res = await client.post(
        "/api/v1/shared/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert res.status_code == 401


# ── Register Validation ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_weak_password_no_uppercase(client: AsyncClient):
    """Büyük harf içermeyen şifre 422 dönmeli."""
    res = await client.post(
        "/api/v1/client/auth/register",
        json={"email": "weak1@example.com", "password": "weakpass1"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_register_weak_password_no_digit(client: AsyncClient):
    """Rakam içermeyen şifre 422 dönmeli."""
    res = await client.post(
        "/api/v1/client/auth/register",
        json={"email": "weak2@example.com", "password": "WeakPassword"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_register_password_too_short(client: AsyncClient):
    """8 karakterden kısa şifre 422 dönmeli."""
    res = await client.post(
        "/api/v1/client/auth/register",
        json={"email": "weak3@example.com", "password": "Sh0rt"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_email(client: AsyncClient):
    """Geçersiz email formatı 422 dönmeli."""
    res = await client.post(
        "/api/v1/client/auth/register",
        json={"email": "not-an-email", "password": "StrongPass1"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_register_without_full_name(client: AsyncClient):
    """full_name opsiyonel — gönderilmese de 201 dönmeli."""
    res = await client.post(
        "/api/v1/client/auth/register",
        json={"email": "nofullname@example.com", "password": "StrongPass1"},
    )
    assert res.status_code == 201
    assert res.json()["full_name"] is None


# ── Auth Edge Cases ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_deactivated_user(client: AsyncClient, db_session: AsyncSession):
    """Deaktif edilmiş kullanıcı giriş yapamamalı."""
    await client.post(
        "/api/v1/client/auth/register",
        json={"email": "inactive@example.com", "password": "StrongPass1"},
    )
    await db_session.execute(
        sa_update(User).where(User.email == "inactive@example.com").values(is_active=False)
    )
    db_session.expire_all()

    res = await client.post(
        "/api/v1/client/auth/login",
        json={"email": "inactive@example.com", "password": "StrongPass1"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_access_token_fails(client: AsyncClient):
    """Access token'ı refresh token olarak kullanmak 401 dönmeli."""
    tokens = await _register_and_login(client, "wrong_token_type@example.com")

    # Access token'ı refresh endpoint'ine gönder — type=ACCESS, REFRESH bekleniyor
    res = await client.post(
        "/api/v1/shared/auth/refresh",
        json={"refresh_token": tokens["access_token"]},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_logout_without_refresh_token(client: AsyncClient):
    """Refresh token olmadan logout 200 dönmeli — access token yine de blacklist'e girmeli."""
    tokens = await _register_and_login(client, "logout_no_refresh@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    res = await client.post(
        "/api/v1/shared/auth/logout",
        json={},  # refresh_token gönderilmiyor
        headers=headers,
    )
    assert res.status_code == 200

    # Access token artık geçersiz olmalı
    me = await client.get("/api/v1/shared/me", headers=headers)
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_login_invalid_email_format(client: AsyncClient):
    """Geçersiz email formatı ile login → 422."""
    res = await client.post(
        "/api/v1/client/auth/login",
        json={"email": "not-an-email", "password": "StrongPass1"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_refresh_garbage_token(client: AsyncClient):
    """Rastgele string ile /refresh → 401."""
    res = await client.post(
        "/api/v1/shared/auth/refresh",
        json={"refresh_token": "garbage.token.string"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_resend_verification_already_verified_sends_no_email(
    client: AsyncClient,
    fake_redis: fakeredis_aioredis.FakeRedis,
    mock_enqueue: AsyncMock,
):
    """Zaten doğrulanmış kullanıcı için resend 200 dönmeli ama email gitmemeli."""
    await client.post(
        "/api/v1/client/auth/register",
        json={"email": "alreadyverified@example.com", "password": "StrongPass1"},
    )
    verify_token = mock_enqueue.call_args.args[2]
    await client.post("/api/v1/client/auth/verify-email", json={"token": verify_token})

    mock_enqueue.reset_mock()

    res = await client.post(
        "/api/v1/client/auth/resend-verification",
        json={"email": "alreadyverified@example.com"},
    )
    assert res.status_code == 200
    mock_enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_verify_email_already_verified_user_still_succeeds(
    client: AsyncClient,
    fake_redis: fakeredis_aioredis.FakeRedis,
    mock_enqueue: AsyncMock,
):
    """
    Zaten doğrulanmış kullanıcıya ait geçerli token ile doğrulama yapıldığında
    200 dönmeli ve token tüketilmeli.

    AccountService.verify_email() token'ı koşulsuz siler, is_verified kontrolü
    güncellemeyi atlar — ancak hata fırlatmaz.
    """
    from app.services._keys import EMAIL_VERIFY_KEY

    await client.post(
        "/api/v1/client/auth/register",
        json={"email": "already_ver2@example.com", "password": "StrongPass1"},
    )
    # İlk doğrulama token'ını al ve doğrula
    first_token = mock_enqueue.call_args.args[2]
    await client.post("/api/v1/client/auth/verify-email", json={"token": first_token})

    # Kullanıcının ID'sini al
    login = await client.post(
        "/api/v1/client/auth/login",
        json={"email": "already_ver2@example.com", "password": "StrongPass1"},
    )
    access_token = login.json()["access_token"]
    me = await client.get("/api/v1/shared/me", headers={"Authorization": f"Bearer {access_token}"})
    user_id = me.json()["id"]

    # Zaten doğrulanmış kullanıcı için Redis'e ikinci bir token ekle
    second_token = "second-verify-token-xyz"
    await fake_redis.setex(EMAIL_VERIFY_KEY.format(second_token), 86400, user_id)

    # Zaten doğrulanmış kullanıcıyla ikinci doğrulama → 200, token silinmeli
    res = await client.post("/api/v1/client/auth/verify-email", json={"token": second_token})
    assert res.status_code == 200
    assert await fake_redis.get(EMAIL_VERIFY_KEY.format(second_token)) is None


@pytest.mark.asyncio
async def test_login_with_wrong_totp_backup_code(client: AsyncClient) -> None:
    """Geçersiz backup kod ile totp-challenge → 401."""
    import pyotp

    email = "totp_bad_backup@example.com"
    password = "StrongPass1"
    tokens = await _register_and_login(client, email)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # 2FA kur ve etkinleştir
    setup_res = await client.post("/api/v1/shared/auth/totp/setup", headers=headers)
    secret = setup_res.json()["secret"]
    valid_code = pyotp.TOTP(secret).now()
    await client.post("/api/v1/shared/auth/totp/verify", json={"code": valid_code}, headers=headers)

    # Adım 1: partial_token al
    step1 = await client.post(
        "/api/v1/client/auth/login",
        json={"email": email, "password": password},
    )
    assert step1.status_code == 200
    assert step1.json()["requires_totp"] is True
    partial_token = step1.json()["partial_token"]

    # Adım 2: Geçersiz backup kod ile challenge → 401
    res = await client.post(
        "/api/v1/shared/auth/totp-challenge",
        json={"partial_token": partial_token, "code": "INVALID1"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_totp_challenge_invalid_partial_token(client: AsyncClient) -> None:
    """Geçersiz partial_token ile totp-challenge → 401."""
    res = await client.post(
        "/api/v1/shared/auth/totp-challenge",
        json={"partial_token": "nonexistent_token", "code": "123456"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_totp_challenge_single_use(client: AsyncClient) -> None:
    """Aynı partial_token ile iki kez challenge → ikincisi 401."""
    import pyotp

    email = "totp_single_use@example.com"
    password = "StrongPass1"
    tokens = await _register_and_login(client, email)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    setup_res = await client.post("/api/v1/shared/auth/totp/setup", headers=headers)
    secret = setup_res.json()["secret"]
    valid_code = pyotp.TOTP(secret).now()
    await client.post("/api/v1/shared/auth/totp/verify", json={"code": valid_code}, headers=headers)

    step1 = await client.post(
        "/api/v1/client/auth/login",
        json={"email": email, "password": password},
    )
    partial_token = step1.json()["partial_token"]

    totp = pyotp.TOTP(secret)
    code = totp.now()

    first = await client.post(
        "/api/v1/shared/auth/totp-challenge",
        json={"partial_token": partial_token, "code": code},
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/v1/shared/auth/totp-challenge",
        json={"partial_token": partial_token, "code": code},
    )
    assert second.status_code == 401


@pytest.mark.asyncio
async def test_totp_two_step_login_success(client: AsyncClient) -> None:
    """TOTP aktif kullanıcı için iki adımlı login başarılı."""
    import pyotp

    email = "totp_two_step@example.com"
    password = "StrongPass1"
    tokens = await _register_and_login(client, email)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    setup_res = await client.post("/api/v1/shared/auth/totp/setup", headers=headers)
    secret = setup_res.json()["secret"]
    valid_code = pyotp.TOTP(secret).now()
    await client.post("/api/v1/shared/auth/totp/verify", json={"code": valid_code}, headers=headers)

    # Adım 1
    step1 = await client.post(
        "/api/v1/client/auth/login",
        json={"email": email, "password": password},
    )
    assert step1.status_code == 200
    data1 = step1.json()
    assert data1["requires_totp"] is True
    assert "partial_token" in data1

    # Adım 2
    step2 = await client.post(
        "/api/v1/shared/auth/totp-challenge",
        json={"partial_token": data1["partial_token"], "code": pyotp.TOTP(secret).now()},
    )
    assert step2.status_code == 200
    data2 = step2.json()
    assert "access_token" in data2
    assert "refresh_token" in data2


@pytest.mark.asyncio
async def test_totp_challenge_sets_cookies(client: AsyncClient) -> None:
    """TOTP challenge başarılı olduğunda httpOnly cookie'ler set edilmeli."""
    import pyotp

    email = "totp_cookie@example.com"
    password = "StrongPass1"
    tokens = await _register_and_login(client, email)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    setup_res = await client.post("/api/v1/shared/auth/totp/setup", headers=headers)
    secret = setup_res.json()["secret"]
    valid_code = pyotp.TOTP(secret).now()
    await client.post("/api/v1/shared/auth/totp/verify", json={"code": valid_code}, headers=headers)

    # Adım 1: partial_token al (cookie yok, requires_totp)
    step1 = await client.post(
        "/api/v1/client/auth/login",
        json={"email": email, "password": password},
    )
    assert step1.status_code == 200
    # TOTP aktif olduğunda cookie set edilmemeli
    assert "access_token" not in step1.cookies

    # Adım 2: TOTP challenge (cookie set edilmeli)
    step2 = await client.post(
        "/api/v1/shared/auth/totp-challenge",
        json={"partial_token": step1.json()["partial_token"], "code": pyotp.TOTP(secret).now()},
    )
    assert step2.status_code == 200
    assert "access_token" in step2.cookies
    assert "refresh_token" in step2.cookies
