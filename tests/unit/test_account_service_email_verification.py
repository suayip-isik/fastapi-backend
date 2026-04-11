"""AccountService email verification branch testleri."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import settings
from app.core.exceptions import InvalidTokenError
from app.db.models.audit_log import AuditAction
from app.services._keys import EMAIL_VERIFY_KEY, encode_email_verify_value
from app.services.account import AccountService


def _build_service() -> tuple[AccountService, AsyncMock, AsyncMock, AsyncMock]:
    audit = AsyncMock()
    redis = AsyncMock()
    task_queue = AsyncMock()
    service = AccountService(AsyncMock(), audit=audit, redis=redis, task_queue=task_queue)
    service._repo = AsyncMock()
    return service, audit, redis, task_queue


@pytest.mark.asyncio
async def test_verify_email_promotes_pending_email() -> None:
    """Pending email doğrulanınca aktif email olarak promote edilmeli."""
    service, audit, redis, _task_queue = _build_service()
    user_id = uuid4()
    token = "verify-token"
    redis.get.return_value = encode_email_verify_value(str(user_id), "New@Example.com")
    service._repo.get_by_id.return_value = SimpleNamespace(
        id=user_id,
        email="old@example.com",
        pending_email="new@example.com",
        is_verified=False,
    )

    await service.verify_email(token)

    redis.delete.assert_awaited_once_with(EMAIL_VERIFY_KEY.format(token))
    service._repo.update.assert_awaited_once_with(
        user_id,
        email="new@example.com",
        pending_email=None,
        is_verified=True,
    )
    audit.log.assert_awaited_once()
    assert audit.log.await_args.args[0] == AuditAction.EMAIL_CHANGED


@pytest.mark.asyncio
async def test_verify_email_rejects_target_email_mismatch() -> None:
    """Token email'i kullanıcı state'i ile eşleşmiyorsa invalid token dönmeli."""
    service, _audit, redis, _task_queue = _build_service()
    user_id = uuid4()
    redis.get.return_value = encode_email_verify_value(str(user_id), "new@example.com")
    service._repo.get_by_id.return_value = SimpleNamespace(
        id=user_id,
        email="old@example.com",
        pending_email="other@example.com",
        is_verified=False,
    )

    with pytest.raises(InvalidTokenError):
        await service.verify_email("verify-token")


@pytest.mark.asyncio
async def test_verify_email_marks_existing_email_as_verified_without_target_email() -> None:
    """Legacy verify token mevcut email doğrulama akışını korumalı."""
    service, audit, redis, _task_queue = _build_service()
    user_id = uuid4()
    redis.get.return_value = str(user_id)
    service._repo.get_by_id.return_value = SimpleNamespace(
        id=user_id,
        email="user@example.com",
        pending_email=None,
        is_verified=False,
    )

    await service.verify_email("legacy-token")

    service._repo.update.assert_awaited_once_with(user_id, is_verified=True)
    assert audit.log.await_args.args[0] == AuditAction.EMAIL_VERIFIED


@pytest.mark.asyncio
async def test_resend_verification_uses_pending_email_when_present() -> None:
    """Pending email lookup bulunduğunda doğrulama maili pending adrese gitmeli."""
    service, audit, redis, task_queue = _build_service()
    user_id = uuid4()
    service._repo.get_active_by_email.return_value = None
    service._repo.get_active_by_pending_email.return_value = SimpleNamespace(
        id=user_id,
        email="old@example.com",
        pending_email="pending@example.com",
        is_verified=True,
    )

    with patch("app.services.account.secrets.token_urlsafe", return_value="resend-token"):
        await service.resend_verification("Pending@Example.com")

    redis.setex.assert_awaited_once_with(
        EMAIL_VERIFY_KEY.format("resend-token"),
        settings.EMAIL_VERIFY_TTL,
        encode_email_verify_value(str(user_id), "pending@example.com"),
    )
    task_queue.enqueue.assert_awaited_once()
    assert task_queue.enqueue.await_args.args[1] == "pending@example.com"
    assert audit.log.await_args.args[0] == AuditAction.VERIFICATION_RESENT
