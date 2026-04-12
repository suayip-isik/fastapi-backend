"""
Alembic async migration ortamı.
Tüm modelleri otomatik algılar (autogenerate).
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import settings

# Tüm modelleri import et — autogenerate için şart
from app.db.models.api_key import APIKey  # noqa: F401
from app.db.models.audit_log import AuditLog  # noqa: F401
from app.db.models.base import Base
from app.db.models.notification import Notification  # noqa: F401
from app.db.models.role import Role, RolePermission  # noqa: F401
from app.db.models.totp_backup_code import TOTPBackupCode  # noqa: F401
from app.db.models.user import User  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Offline modda migration çalıştırır (SQL script üretir).

    Veritabanına bağlanmadan SQL scriptleri üretir. CI/CD pipeline'ında
    veya manuel review için kullanılır.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Senkron bağlantı ile migration'ları çalıştırır."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Async engine ile migration'ları çalıştırır."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Online modda migration çalıştırır (veritabanına bağlanır)."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
