"""OpenAPI surface ayrımı testleri."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select
from sqlalchemy import update as sa_update

from app.db.models.role import Role
from app.db.models.user import AccountType, User

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def _promote_to_admin(db_session: AsyncSession, email: str) -> None:
    result = await db_session.execute(select(Role.id).where(Role.name == "admin"))
    admin_role_id = result.scalar_one()
    await db_session.execute(
        sa_update(User)
        .where(User.email == email)
        .values(role_id=admin_role_id, account_type=AccountType.ADMIN.value)
    )
    await db_session.commit()
    db_session.expire_all()


@pytest.mark.asyncio
async def test_client_openapi_contains_client_and_shared_not_admin(client: AsyncClient) -> None:
    res = await client.get("/schema/client/openapi.json")
    assert res.status_code == 200
    paths = res.json()["paths"]
    assert "/api/v1/client/auth/login" in paths
    assert "/api/v1/shared/auth/forgot-password" in paths
    assert "/api/v1/shared/auth/reset-password" in paths
    assert "/api/v1/shared/me" in paths
    assert "/api/v1/admin/users" not in paths
    assert "/api/v1/admin/auth/login" not in paths
    assert "/api/v1/client/auth/forgot-password" not in paths
    assert "/api/v1/client/auth/reset-password" not in paths


@pytest.mark.asyncio
async def test_admin_openapi_contains_admin_and_shared_not_client(client: AsyncClient) -> None:
    res = await client.get("/schema/admin/openapi.json")
    assert res.status_code == 200
    paths = res.json()["paths"]
    assert "/api/v1/admin/users" in paths
    assert "/api/v1/admin/auth/login" in paths
    assert "/api/v1/shared/auth/forgot-password" in paths
    assert "/api/v1/shared/auth/reset-password" in paths
    assert "/api/v1/shared/me" in paths
    assert "/api/v1/client/auth/login" not in paths
    assert "/api/v1/client/auth/forgot-password" not in paths
    assert "/api/v1/admin/auth/forgot-password" not in paths
    assert "/api/v1/admin/auth/reset-password" not in paths


@pytest.mark.asyncio
async def test_shared_password_reset_routes_are_tagged_shared_in_both_schemas(
    client: AsyncClient,
) -> None:
    for schema_path in ("/schema/client/openapi.json", "/schema/admin/openapi.json"):
        res = await client.get(schema_path)
        assert res.status_code == 200
        paths = res.json()["paths"]
        assert paths["/api/v1/shared/auth/forgot-password"]["post"]["tags"] == ["Shared Auth"]
        assert paths["/api/v1/shared/auth/reset-password"]["post"]["tags"] == ["Shared Auth"]


@pytest.mark.asyncio
async def test_legacy_openapi_aliases_are_removed(client: AsyncClient) -> None:
    user_schema = await client.get("/schema/user/openapi.json")
    mobile_schema = await client.get("/schema/mobile/openapi.json")

    assert user_schema.status_code == 404
    assert mobile_schema.status_code == 404


@pytest.mark.asyncio
async def test_surface_docs_endpoints_are_available(client: AsyncClient) -> None:
    for path in ("/schema/client/docs", "/schema/admin/docs"):
        res = await client.get(path)
        assert res.status_code == 200
        assert "Swagger UI" in res.text


@pytest.mark.asyncio
async def test_legacy_routes_are_removed(client: AsyncClient) -> None:
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "wrong"},
    )
    me_res = await client.get("/api/v1/users/me")
    forgot_res = await client.post(
        "/api/v1/client/auth/forgot-password",
        json={"email": "nobody@example.com"},
    )
    admin_reset_res = await client.post(
        "/api/v1/admin/auth/reset-password",
        json={"token": "bad-token-xyz", "new_password": "NewStrongPass2"},
    )

    assert login_res.status_code == 404
    assert me_res.status_code == 404
    assert forgot_res.status_code == 404
    assert admin_reset_res.status_code == 404


@pytest.mark.asyncio
async def test_admin_token_from_admin_login_can_access_admin_and_shared(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    email = "surface-admin@example.com"
    password = "StrongPass1"

    await client.post("/api/v1/client/auth/register", json={"email": email, "password": password})
    await _promote_to_admin(db_session, email)

    login = await client.post(
        "/api/v1/admin/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    me_res = await client.get("/api/v1/shared/me", headers=headers)
    users_res = await client.get("/api/v1/admin/users", headers=headers)

    assert me_res.status_code == 200
    assert me_res.json()["account_type"] == AccountType.ADMIN.value
    assert users_res.status_code == 200


@pytest.mark.asyncio
async def test_client_token_cannot_access_admin_surface(client: AsyncClient) -> None:
    email = "surface-client@example.com"
    password = "StrongPass1"

    await client.post("/api/v1/client/auth/register", json={"email": email, "password": password})
    login = await client.post(
        "/api/v1/client/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    admin_res = await client.get("/api/v1/admin/users", headers=headers)
    shared_res = await client.get("/api/v1/shared/me", headers=headers)

    assert admin_res.status_code == 403
    assert shared_res.status_code == 200
    assert shared_res.json()["account_type"] == AccountType.CLIENT.value
