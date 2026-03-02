"""
ARQ background task'ları.
Redis-based, async, lightweight — Celery'ye göre daha sade.
"""
from __future__ import annotations

import asyncio
from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import settings
from app.core.email import send_email
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Redis Settings ────────────────────────────────────────────────────────────

def get_redis_settings() -> RedisSettings:
    return RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD or None,
        database=settings.REDIS_DB,
    )


# ── Task Functions ────────────────────────────────────────────────────────────

async def send_welcome_email(ctx: dict, user_id: str, email: str) -> dict:
    """
    Hoşgeldiniz e-postası gönder.
    ctx: ARQ tarafından inject edilen context (DB, Redis vs.)
    """
    logger.info("sending_welcome_email", user_id=user_id, email=email)
    # TODO: SMTP entegrasyonu
    await asyncio.sleep(0.1)  # Simulate email send
    logger.info("welcome_email_sent", user_id=user_id)
    return {"status": "sent", "user_id": user_id}


async def process_file_upload(ctx: dict, file_key: str, user_id: str) -> dict:
    """
    Dosya yükleme sonrası işlemler.
    Örn: thumbnail oluşturma, virus tarama, metadata çıkarma.
    """
    logger.info("processing_upload", file_key=file_key, user_id=user_id)
    await asyncio.sleep(0.1)  # Simulate processing
    return {"status": "processed", "file_key": file_key}


async def send_verification_email(ctx: dict, email: str, token: str) -> dict:
    """E-posta doğrulama linki gönder."""
    logger.info("sending_verification_email", email=email)
    verify_url = f"{settings.APP_URL}/api/v1/auth/verify-email?token={token}"
    await send_email(
        to=email,
        subject="E-posta adresinizi doğrulayın",
        html_body=(
            f"<p>Hesabınızı doğrulamak için "
            f"<a href='{verify_url}'>buraya tıklayın</a>.</p>"
            f"<p>Bu link 24 saat geçerlidir.</p>"
        ),
    )
    logger.info("verification_email_sent", email=email)
    return {"status": "sent", "email": email}


async def send_password_reset_email(ctx: dict, email: str, token: str) -> dict:
    """Şifre sıfırlama linki gönder."""
    logger.info("sending_password_reset_email", email=email)
    reset_url = f"{settings.APP_URL}/api/v1/auth/reset-password?token={token}"
    await send_email(
        to=email,
        subject="Şifre sıfırlama isteği",
        html_body=(
            f"<p>Şifrenizi sıfırlamak için "
            f"<a href='{reset_url}'>buraya tıklayın</a>.</p>"
            f"<p>Bu link 15 dakika geçerlidir.</p>"
        ),
    )
    logger.info("password_reset_email_sent", email=email)
    return {"status": "sent", "email": email}


async def cleanup_expired_tokens(ctx: dict) -> dict:
    """
    Süresi dolmuş refresh token'ları temizle.
    Cron job olarak çalışır.
    """
    logger.info("cleaning_expired_tokens")
    # TODO: DB'den süresi dolmuş token'ları sil
    return {"status": "cleaned"}


# ── Worker Config ─────────────────────────────────────────────────────────────

class WorkerSettings:
    """ARQ worker ayarları."""

    functions = [
        send_welcome_email,
        process_file_upload,
        cleanup_expired_tokens,
        send_verification_email,
        send_password_reset_email,
    ]

    # Cron jobs
    cron_jobs = [
        # Her gece yarısı token temizliği
        # cron(cleanup_expired_tokens, hour=0, minute=0),
    ]

    redis_settings = get_redis_settings()

    max_jobs = 10
    job_timeout = 300  # 5 dakika


# ── Pool Helper ───────────────────────────────────────────────────────────────

_arq_pool: ArqRedis | None = None


async def get_task_queue() -> ArqRedis:
    """FastAPI Depends() ile kullanılabilir task queue."""
    global _arq_pool
    if _arq_pool is None:
        _arq_pool = await create_pool(get_redis_settings())
    return _arq_pool


async def enqueue(task_func, *args: Any, **kwargs: Any) -> None:
    """Task kuyruğa ekle."""
    pool = await get_task_queue()
    await pool.enqueue_job(task_func.__name__, *args, **kwargs)
