"""Auth endpoint testleri."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    res = await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "StrongPass1",
        "full_name": "Test User",
    })
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "test@example.com"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    payload = {"email": "dup@example.com", "password": "StrongPass1"}
    await client.post("/api/v1/auth/register", json=payload)
    res = await client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "login@example.com",
        "password": "StrongPass1",
    })
    res = await client.post("/api/v1/auth/login", json={
        "email": "login@example.com",
        "password": "StrongPass1",
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    res = await client.post("/api/v1/auth/login", json={
        "email": "nonexistent@example.com",
        "password": "WrongPass1",
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient):
    # Register + login
    await client.post("/api/v1/auth/register", json={
        "email": "me@example.com",
        "password": "StrongPass1",
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": "me@example.com",
        "password": "StrongPass1",
    })
    token = login.json()["access_token"]

    res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    res = await client.get("/api/v1/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
