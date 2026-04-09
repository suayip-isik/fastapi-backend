"""Email gönderim modülü.

Bu modül SMTP üzerinden asenkron email gönderimi için utility fonksiyonları sağlar.
aiosmtplib kütüphanesi kullanılarak async/await desteği ile email gönderilir.

Güvenlik ve Stabilite:
    - Email body asla loglanmaz (doğrulama/sıfırlama token'ları içerebilir)
    - SMTP hatalarında exception fırlatılmaz (API akışı kesintiye uğramaz)
    - Development ortamında SMTP olmadan link extraction ile test edilebilir

Yapılandırma:
    Email ayarları app.core.config.Settings üzerinden yapılır:
    - SMTP_HOST: SMTP sunucu adresi (boşsa dev fallback aktif)
    - SMTP_PORT: SMTP port (varsayılan 587)
    - SMTP_USER: SMTP kimlik doğrulama kullanıcı adı
    - SMTP_PASSWORD: SMTP kimlik doğrulama şifresi
    - EMAILS_FROM_EMAIL: Gönderen email adresi

Dev Fallback:
    SMTP_HOST yapılandırılmamışsa (development/test ortamı) email gönderilmez,
    bunun yerine HTML içeriğindeki ilk link parse edilip log'a yazılır.
    Bu sayede geliştirme ortamında doğrulama/sıfırlama linkleri görülebilir.

Note:
    Production ortamında background task (ARQ) ile kullanılmalıdır.
    Retry mechanism bu modülde yok, task queue'da yapılandırılmalı.
"""

from __future__ import annotations

import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# href değerlerini çekmeye yarayan pattern
_HREF_RE = re.compile(r"""href=['"]([^'"]+)['"]""")


async def send_email(*, to: str, subject: str, html_body: str) -> None:
    """SMTP üzerinden HTML email gönderir (async).

    aiosmtplib kullanarak asenkron email gönderimi yapar. SMTP ayarları
    Settings'den (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD) alınır.

    SMTP_HOST yapılandırılmamışsa (dev/test ortamı) email gönderimi yapılmaz,
    bunun yerine HTML içeriğindeki linkler parse edilip ilk link log'a yazılır.
    Bu sayede geliştirme ortamında doğrulama/sıfırlama linkleri console'da görünür.

    SMTP gönderimi başarısız olursa exception fırlatır. Bu exception worker
    tarafından loglanır ve job başarısız sayılır; API akışı yine etkilenmez
    çünkü email işi background task ile yürütülür.

    Args:
        to: Alıcı email adresi (tek alıcı)
        subject: Email başlığı
        html_body: HTML formatında email içeriği (doğrulama/sıfırlama token'ları
            içerebilir, güvenlik nedeniyle asla loglanmaz)

    Returns:
        None

    Example:
        >>> await send_email(
        ...     to="user@example.com",
        ...     subject="Email Doğrulama",
        ...     html_body="<h1>Hoş Geldiniz</h1><a href='http://...'>Doğrula</a>"
        ... )

    Note:
        - Production'da gerçek SMTP kullanılır (TLS ile)
        - Development'ta SMTP_HOST boşsa console'a dev_link log yazılır
        - Email body asla loglanmaz (güvenlik - token içerebilir)
        - Retry mechanism yok, background task (ARQ) ile kullanılmalı
        - SMTP hataları worker katmanına propagate edilir
    """
    if not settings.SMTP_HOST:
        links = _HREF_RE.findall(html_body)
        logger.warning(
            "smtp_not_configured_dev_fallback",
            to=to,
            subject=subject,
            dev_link=links[0] if links else None,
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
        raise
