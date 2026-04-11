"""Alembic revision drift kontrolü."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from alembic.config import Config
from alembic.script import ScriptDirectory
from app.core.exceptions import ConfigurationError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine


class DatabaseSchemaMismatchError(ConfigurationError):
    """Uygulama kodu ile veritabanı şeması uyuşmadığında fırlatılır."""

    code = "DATABASE_SCHEMA_MISMATCH"
    message = "Veritabanı şeması uygulama sürümü ile uyumlu değil."


def _project_root() -> Path:
    """Repo kök dizinini döndürür."""
    return Path(__file__).resolve().parents[2]


def get_alembic_config() -> Config:
    """Repo kökündeki alembic.ini üzerinden config oluşturur."""
    project_root = _project_root()
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "alembic"))
    return config


def get_expected_revision_heads() -> set[str]:
    """Kodun beklediği Alembic head revision'larını döndürür."""
    script = ScriptDirectory.from_config(get_alembic_config())
    return set(script.get_heads())


async def get_current_revision_heads(engine: AsyncEngine) -> set[str]:
    """Veritabanındaki mevcut Alembic revision'larını döndürür."""
    async with engine.connect() as connection:
        try:
            result = await connection.execute(text("SELECT version_num FROM alembic_version"))
        except DBAPIError as exc:
            raise DatabaseSchemaMismatchError(
                "Alembic version tablosu okunamadı. Önce migration'ları çalıştırın."
            ) from exc
    return set(result.scalars().all())


async def validate_database_schema(engine: AsyncEngine) -> None:
    """Uygulama startup'ında veritabanı revision'ının head ile eşleştiğini doğrular."""
    expected_heads = get_expected_revision_heads()
    current_heads = await get_current_revision_heads(engine)

    if current_heads != expected_heads:
        raise DatabaseSchemaMismatchError(
            "Veritabanı revision'ı güncel değil. "
            f"Beklenen head: {sorted(expected_heads)}, mevcut: {sorted(current_heads)}. "
            "Deploy öncesi `alembic upgrade head` çalıştırın."
        )
