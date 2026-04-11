"""Worker task unit testleri."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.tasks.worker import (
    send_admin_invite_email,
    send_admin_password_reset_email,
    send_password_reset_email,
)


@pytest.mark.asyncio
async def test_send_password_reset_email_uses_frontend_reset_route() -> None:
    """Password reset email frontend reset sayfasına yönlenmeli."""
    with (
        patch("app.tasks.worker.settings.FRONTEND_URL", "http://localhost:3000"),
        patch("app.tasks.worker.send_email", new_callable=AsyncMock) as mock_send_email,
    ):
        await send_password_reset_email({}, "user@example.com", "token-123", "en")

    mock_send_email.assert_awaited_once()
    assert (
        mock_send_email.await_args.kwargs["html_body"].find(
            "http://localhost:3000/reset-password?token=token-123"
        )
        != -1
    )


@pytest.mark.asyncio
async def test_send_admin_invite_email_uses_frontend_reset_route() -> None:
    """Admin invite email de frontend reset sayfasına yönlenmeli."""
    with (
        patch("app.tasks.worker.settings.FRONTEND_URL", "http://localhost:3000"),
        patch("app.tasks.worker.send_email", new_callable=AsyncMock) as mock_send_email,
    ):
        await send_admin_invite_email({}, "admin@example.com", "token-456", "en")

    mock_send_email.assert_awaited_once()
    assert mock_send_email.await_args.kwargs["subject"] == "Set your admin account password"
    assert (
        mock_send_email.await_args.kwargs["html_body"].find(
            "http://localhost:3000/reset-password?token=token-456&surface=admin"
        )
        != -1
    )


@pytest.mark.asyncio
async def test_send_admin_password_reset_email_uses_admin_surface_reset_route() -> None:
    """Admin reset email shared frontend sayfasına admin surface bilgisiyle yönlenmeli."""
    with (
        patch("app.tasks.worker.settings.FRONTEND_URL", "http://localhost:3000"),
        patch("app.tasks.worker.send_email", new_callable=AsyncMock) as mock_send_email,
    ):
        await send_admin_password_reset_email({}, "admin@example.com", "token-789", "en")

    mock_send_email.assert_awaited_once()
    assert mock_send_email.await_args.kwargs["subject"] == "Admin password reset request"
    assert (
        mock_send_email.await_args.kwargs["html_body"].find(
            "http://localhost:3000/reset-password?token=token-789&surface=admin"
        )
        != -1
    )
