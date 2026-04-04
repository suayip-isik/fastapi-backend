"""
Audit log integration testleri.

AuditService, AsyncSessionFactory kullandığından test DB'sine değil main DB'ye yazar.
Bu nedenle _audit_log çağrıları mock'lanır; doğru aksiyon ve user_id ile çağrıldığı assert edilir.
Bu yaklaşım projede kullanılan mock_enqueue pattern'ıyla tutarlıdır.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.db.models.audit_log import AuditAction

_PASSWORD = "StrongPass1!"


async def _register(client: AsyncClient, email: str) -> None:
    """Yardımcı fonksiyon."""
    await client.post("/api/v1/auth/register", json={"email": email, "password": _PASSWORD})


async def _login_tokens(client: AsyncClient, email: str) -> dict:
    """Yardımcı fonksiyon."""
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": _PASSWORD})
    return res.json()


@pytest.fixture
def mock_audit() -> AsyncMock:
    """AuditableMixin._audit_log'u mock'la — test süresi boyunca tüm servisler etkiler."""
    with patch(
        "app.services.base.AuditableMixin._audit_log",
        new_callable=AsyncMock,
    ) as m:
        yield m


def _called_actions(mock: AsyncMock) -> list[AuditAction]:
    """Mock'a geçirilen tüm 'action' argümanlarını toplar."""
    actions = []
    for c in mock.call_args_list:
        action = c.kwargs.get("action") or (c.args[0] if c.args else None)
        if action is not None:
            actions.append(action)
    return actions


class TestRegisterAudit:
    """TestRegisterAudit test grubunu içerir."""

    async def test_register_triggers_register_audit_action(
        self, client: AsyncClient, mock_audit: AsyncMock
    ) -> None:
        """Başarılı kayıt → REGISTER aksiyonu audit edilmeli."""
        await _register(client, "audit_reg@test.com")
        assert AuditAction.REGISTER in _called_actions(mock_audit)

    async def test_register_audit_includes_user_id(
        self, client: AsyncClient, mock_audit: AsyncMock
    ) -> None:
        """REGISTER audit çağrısında user_id None olmamalı."""
        await _register(client, "audit_reg_uid@test.com")
        register_calls = [
            c
            for c in mock_audit.call_args_list
            if (c.kwargs.get("action") or (c.args[0] if c.args else None)) == AuditAction.REGISTER
        ]
        assert register_calls, "REGISTER audit çağrısı bulunamadı"
        user_id = register_calls[0].kwargs.get("user_id")
        assert user_id is not None


class TestLoginAudit:
    """TestLoginAudit test grubunu içerir."""

    async def test_successful_login_triggers_login_success_audit(
        self, client: AsyncClient, mock_audit: AsyncMock
    ) -> None:
        """Başarılı giriş → LOGIN_SUCCESS aksiyonu audit edilmeli."""
        await _register(client, "audit_login@test.com")
        mock_audit.reset_mock()
        await client.post(
            "/api/v1/auth/login", json={"email": "audit_login@test.com", "password": _PASSWORD}
        )
        assert AuditAction.LOGIN_SUCCESS in _called_actions(mock_audit)

    async def test_failed_login_triggers_login_failed_audit(
        self, client: AsyncClient, mock_audit: AsyncMock
    ) -> None:
        """Hatalı giriş → LOGIN_FAILED aksiyonu audit edilmeli."""
        await client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent_audit@test.com", "password": "wrong"},
        )
        assert AuditAction.LOGIN_FAILED in _called_actions(mock_audit)

    async def test_login_success_audit_has_user_id(
        self, client: AsyncClient, mock_audit: AsyncMock
    ) -> None:
        """LOGIN_SUCCESS audit çağrısında user_id dolu olmalı."""
        await _register(client, "audit_uid@test.com")
        mock_audit.reset_mock()
        await client.post(
            "/api/v1/auth/login", json={"email": "audit_uid@test.com", "password": _PASSWORD}
        )
        success_calls = [
            c
            for c in mock_audit.call_args_list
            if (c.kwargs.get("action") or (c.args[0] if c.args else None))
            == AuditAction.LOGIN_SUCCESS
        ]
        assert success_calls
        assert success_calls[0].kwargs.get("user_id") is not None


class TestLogoutAudit:
    """TestLogoutAudit test grubunu içerir."""

    async def test_logout_triggers_logout_audit(
        self, client: AsyncClient, mock_audit: AsyncMock
    ) -> None:
        """Çıkış → LOGOUT aksiyonu audit edilmeli."""
        await _register(client, "audit_logout@test.com")
        tokens = await _login_tokens(client, "audit_logout@test.com")
        mock_audit.reset_mock()

        await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": tokens["refresh_token"]},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert AuditAction.LOGOUT in _called_actions(mock_audit)


class TestTokenRefreshAudit:
    """TestTokenRefreshAudit test grubunu içerir."""

    async def test_token_refresh_triggers_audit(
        self, client: AsyncClient, mock_audit: AsyncMock
    ) -> None:
        """Token yenileme → TOKEN_REFRESHED aksiyonu audit edilmeli."""
        await _register(client, "audit_refresh@test.com")
        tokens = await _login_tokens(client, "audit_refresh@test.com")
        mock_audit.reset_mock()

        await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert AuditAction.TOKEN_REFRESHED in _called_actions(mock_audit)
