"""AuthService register davranışı testleri."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import UserAlreadyExistsError
from app.schemas.auth import RegisterRequest
from app.services.auth import AuthService


@pytest.mark.asyncio
async def test_register_maps_integrity_error_to_user_already_exists() -> None:
    """Register insert yarışında duplicate email hatası domain hatasına çevrilmeli."""
    session = AsyncMock()
    service = AuthService(session)
    service._repo = AsyncMock()
    service._repo.email_exists.return_value = False
    service._repo.create.side_effect = IntegrityError("INSERT", {}, Exception("duplicate"))

    data = RegisterRequest(email="duplicate@example.com", password="StrongPass1")

    with pytest.raises(UserAlreadyExistsError):
        await service.register(data)

    session.rollback.assert_awaited_once()
