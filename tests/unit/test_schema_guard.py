"""Schema guard unit testleri."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI

from app.core.exceptions import ConfigurationError
from app.db.schema_guard import (
    DatabaseSchemaMismatchError,
    validate_database_schema,
)
from app.main import lifespan


async def test_validate_database_schema_passes_when_revisions_match() -> None:
    """DB head ile repo head eşleşince guard hata vermemeli."""
    with (
        patch("app.db.schema_guard.get_expected_revision_heads", return_value={"head-1"}),
        patch(
            "app.db.schema_guard.get_current_revision_heads",
            new=AsyncMock(return_value={"head-1"}),
        ),
    ):
        await validate_database_schema(engine=AsyncMock())


async def test_validate_database_schema_raises_on_revision_mismatch() -> None:
    """DB revision geri kaldığında açıklayıcı hata fırlatılmalı."""
    with (
        patch("app.db.schema_guard.get_expected_revision_heads", return_value={"head-new"}),
        patch(
            "app.db.schema_guard.get_current_revision_heads",
            new=AsyncMock(return_value={"head-old"}),
        ),
        pytest.raises(DatabaseSchemaMismatchError, match="alembic upgrade head"),
    ):
        await validate_database_schema(engine=AsyncMock())


async def test_schema_guard_error_is_configuration_error() -> None:
    """Schema drift hatası ConfigurationError hiyerarşisinde kalmalı."""
    assert issubclass(DatabaseSchemaMismatchError, ConfigurationError)


async def test_lifespan_runs_schema_guard_before_seeding() -> None:
    """Startup sırasında schema guard ve seed işlemleri çağrılmalı."""
    validate_schema = AsyncMock()
    seed_roles = AsyncMock()
    create_admin = AsyncMock()
    close_redis = AsyncMock()
    mock_engine = SimpleNamespace(dispose=AsyncMock())

    with (
        patch("app.main.validate_database_schema", validate_schema),
        patch("app.main.seed_system_roles", seed_roles),
        patch("app.main.create_default_admin", create_admin),
        patch("app.main.close_redis", close_redis),
        patch("app.main.engine", mock_engine),
        patch("app.main.settings.ENFORCE_DB_SCHEMA_CHECK", True),
    ):
        async with lifespan(FastAPI()):
            pass

    validate_schema.assert_awaited_once_with(mock_engine)
    seed_roles.assert_awaited_once()
    create_admin.assert_awaited_once()
