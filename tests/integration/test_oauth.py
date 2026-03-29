"""OAuth endpoint testleri — /api/v1/auth/google, /api/v1/auth/github"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, HTTPStatusError

# ── Mock Helpers ──────────────────────────────────────────────────────────────


def _make_response(data: dict | list, status_code: int = 200) -> MagicMock:
    """Fake httpx response oluştur."""
    mock = MagicMock()
    mock.json.return_value = data
    if status_code >= 400:
        mock.raise_for_status.side_effect = HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock(status_code=status_code)
        )
    else:
        mock.raise_for_status = MagicMock()
    return mock


def _mock_httpx_google(
    access_token: str = "google_access_token",
    user_id: str = "google_user_123",
    email: str = "googleuser@gmail.com",
    name: str = "Google User",
) -> AsyncMock:
    """Google OAuth akışı için httpx.AsyncClient mock'u (post + get)."""
    mock_client = AsyncMock()
    mock_client.post.return_value = _make_response({"access_token": access_token})
    mock_client.get.return_value = _make_response(
        {"sub": user_id, "email": email, "name": name, "picture": None}
    )
    return mock_client


def _mock_httpx_github(
    access_token: str = "github_access_token",
    user_id: int = 987654,
    email: str = "githubuser@example.com",
    name: str = "GitHub User",
) -> AsyncMock:
    """GitHub OAuth akışı için httpx.AsyncClient mock'u (post + 2x get)."""
    mock_client = AsyncMock()
    mock_client.post.return_value = _make_response({"access_token": access_token})
    mock_client.get.side_effect = [
        _make_response({"id": user_id, "name": name, "avatar_url": None, "email": email}),
        _make_response([{"email": email, "primary": True}]),
    ]
    return mock_client


def _patch_httpx(mock_client: AsyncMock):
    """app.services.oauth.httpx.AsyncClient'ı context manager mock'u ile patch'le."""
    mock_cls = MagicMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
    return patch("app.services.oauth.httpx.AsyncClient", mock_cls)


# ── Redirect Testleri ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_google_redirect(client: AsyncClient):
    """GET /auth/google → 307 redirect, Location Google URL içermeli."""
    res = await client.get("/api/v1/auth/google", follow_redirects=False)
    assert res.status_code == 307
    assert "accounts.google.com" in res.headers["location"]


@pytest.mark.asyncio
async def test_github_redirect(client: AsyncClient):
    """GET /auth/github → 307 redirect, Location GitHub URL içermeli."""
    res = await client.get("/api/v1/auth/github", follow_redirects=False)
    assert res.status_code == 307
    assert "github.com" in res.headers["location"]


# ── Google Callback ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_google_callback_missing_code(client: AsyncClient):
    """code query param olmadan GET → 422."""
    res = await client.get("/api/v1/auth/google/callback")
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_google_callback_success(client: AsyncClient):
    """Geçerli code ile Google callback → TokenResponse döner."""
    mock_client = _mock_httpx_google()

    with _patch_httpx(mock_client):
        res = await client.get("/api/v1/auth/google/callback?code=valid_code")

    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_google_callback_creates_verified_user(client: AsyncClient):
    """İlk Google girişinde yeni kullanıcı oluşturulur ve is_verified=True olur."""
    mock_client = _mock_httpx_google(email="newgoogle@example.com")

    with _patch_httpx(mock_client):
        res = await client.get("/api/v1/auth/google/callback?code=new_code")

    assert res.status_code == 200
    tokens = res.json()

    me = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "newgoogle@example.com"
    assert me.json()["is_verified"] is True


@pytest.mark.asyncio
async def test_google_callback_existing_user_same_id(client: AsyncClient):
    """Aynı Google hesabıyla ikinci giriş aynı kullanıcıyı döner."""
    mock1 = _mock_httpx_google(user_id="same_google_id", email="repeat_google@example.com")
    with _patch_httpx(mock1):
        res1 = await client.get("/api/v1/auth/google/callback?code=code1")
    assert res1.status_code == 200

    mock2 = _mock_httpx_google(user_id="same_google_id", email="repeat_google@example.com")
    with _patch_httpx(mock2):
        res2 = await client.get("/api/v1/auth/google/callback?code=code2")
    assert res2.status_code == 200

    # Her iki token da aynı kullanıcıyı döndürmeli
    me1 = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {res1.json()['access_token']}"}
    )
    me2 = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {res2.json()['access_token']}"}
    )
    assert me1.json()["id"] == me2.json()["id"]


# ── GitHub Callback ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_github_callback_missing_code(client: AsyncClient):
    """code query param olmadan GET → 422."""
    res = await client.get("/api/v1/auth/github/callback")
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_github_callback_success(client: AsyncClient):
    """Geçerli code ile GitHub callback → TokenResponse döner."""
    mock_client = _mock_httpx_github()

    with _patch_httpx(mock_client):
        res = await client.get("/api/v1/auth/github/callback?code=gh_code")

    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_github_callback_creates_user(client: AsyncClient):
    """İlk GitHub girişinde yeni kullanıcı oluşturulur."""
    mock_client = _mock_httpx_github(email="newgithub@example.com", user_id=111111)

    with _patch_httpx(mock_client):
        res = await client.get("/api/v1/auth/github/callback?code=gh_new")

    assert res.status_code == 200
    tokens = res.json()

    me = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "newgithub@example.com"
    assert me.json()["is_verified"] is True
