"""Destructive reset + canonical reseed integration tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.db.models.audit_log import AuditAction, AuditLog
from app.db.models.role import Role
from app.db.models.user import User
from scripts.reset_system_state import reset_system_state


@pytest.mark.asyncio
async def test_reset_system_state_hard_deletes_existing_users_roles_and_reseeds(
    db_session: AsyncSession,
) -> None:
    extra_role = Role(name="legacy_role", description="legacy", is_system=False)
    db_session.add(extra_role)
    await db_session.flush()

    extra_user = User(
        email="legacy@example.com",
        username="legacy",
        hashed_password="hashed",
        surface="client",
        role_id=extra_role.id,
        is_active=True,
        is_verified=True,
    )
    db_session.add(extra_user)
    await db_session.flush()

    db_session.add(AuditLog(action=AuditAction.LOGIN_SUCCESS, user_id=extra_user.id))
    await db_session.commit()

    test_database_url = settings.DATABASE_URL.replace(f"/{settings.POSTGRES_DB}", "/test_db")
    with patch(
        "scripts.reset_system_state.create_async_engine",
        side_effect=lambda _: create_async_engine(test_database_url),
    ):
        await reset_system_state()

    engine = create_async_engine(test_database_url)
    async with AsyncSession(engine, expire_on_commit=False) as verification_session:
        roles = list(
            (await verification_session.execute(select(Role).order_by(Role.name))).scalars().all()
        )
        users = list(
            (await verification_session.execute(select(User).order_by(User.email))).scalars().all()
        )
        audit_logs = (await verification_session.execute(select(AuditLog))).scalars().all()
    await engine.dispose()

    assert [role.name for role in roles] == ["app_user", "panel_admin"]
    assert [user.email for user in users] == ["suayip@example.com", "superadmin@example.com"]
    assert [user.username for user in users] == ["suayip", "superadmin"]
    assert {user.surface for user in users} == {"client", "admin"}
    assert audit_logs == []
