"""Email utility unit testleri."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.email import send_email


@pytest.mark.asyncio
async def test_send_email_raises_on_smtp_failure() -> None:
    """SMTP başarısızsa exception worker katmanına aktarılmalı."""
    with (
        patch("app.core.email.settings.SMTP_HOST", "smtp.example.com"),
        patch("app.core.email.settings.SMTP_PORT", 587),
        patch("app.core.email.settings.SMTP_USER", "user@example.com"),
        patch("app.core.email.settings.SMTP_PASSWORD", "secret"),
        patch("app.core.email.settings.EMAILS_FROM_EMAIL", "noreply@example.com"),
        patch(
            "app.core.email.aiosmtplib.send",
            new=AsyncMock(side_effect=RuntimeError("smtp auth failed")),
        ),
    ):
        with pytest.raises(RuntimeError, match="smtp auth failed"):
            await send_email(
                to="user@example.com",
                subject="Reset",
                html_body="<a href='http://localhost/reset-password?token=123'>reset</a>",
            )
