"""
E-posta gönderim utility.
SMTP_HOST yapılandırılmamışsa token'ı stdout'a loglar (dev fallback).
Hiçbir zaman exception fırlatmaz — e-posta hatası API akışını kesmemeli.
"""

from __future__ import annotations

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def send_email(*, to: str, subject: str, html_body: str) -> None:
    """
    E-posta gönder.

    SMTP_HOST tanımlı değilse içeriği log'a yazar ve döner (dev mode).
    SMTP hatasında da loglayıp devam eder — asla exception fırlatmaz.
    """
    if not settings.SMTP_HOST:
        logger.warning(
            "smtp_not_configured_dev_fallback",
            to=to,
            subject=subject,
            body=html_body,
        )
        return

    message = MIMEMultipart("alternative")
    message["From"] = settings.EMAILS_FROM_EMAIL
    message["To"] = to
    message["Subject"] = subject
    message.attach(MIMEText(html_body, "html"))

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER or None,
            password=settings.SMTP_PASSWORD or None,
            start_tls=True,
        )
        logger.info("email_sent", to=to, subject=subject)
    except Exception as exc:
        logger.error("email_send_failed", to=to, subject=subject, error=str(exc))
