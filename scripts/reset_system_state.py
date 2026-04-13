"""Hard-delete user/role state and rebuild canonical roles/users.

Usage:
    docker compose exec api python scripts/reset_system_state.py
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.admin.seed import create_default_app_user, create_default_superadmin, seed_system_roles
from app.core.config import settings

TRUNCATE_SQL = """
TRUNCATE TABLE
    audit_logs,
    api_keys,
    notifications,
    totp_backup_codes,
    users,
    role_permissions,
    roles
RESTART IDENTITY CASCADE
"""


async def reset_system_state() -> None:
    """Delete user/role state and rebuild the canonical seed dataset."""
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text(TRUNCATE_SQL))

    await seed_system_roles()
    await create_default_superadmin()
    await create_default_app_user()
    await engine.dispose()


def main() -> None:
    asyncio.run(reset_system_state())


if __name__ == "__main__":
    main()
