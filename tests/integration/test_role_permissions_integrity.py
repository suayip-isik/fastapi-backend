"""role_permissions integrity enforcement testleri."""

from __future__ import annotations

from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError

from app.core.exceptions import BusinessRuleError
from app.db.models.role import Role
from app.db.repositories.role import RoleRepository


@pytest.mark.asyncio
async def test_role_repository_rejects_invalid_permission_values(db_session) -> None:
    role = Role(name="invalid_perm_role", description=None, is_system=False)
    db_session.add(role)
    await db_session.flush()

    repo = RoleRepository(db_session)

    with pytest.raises(BusinessRuleError, match="users:read"):
        await repo.set_permissions(role.id, ["users:read"])


@pytest.mark.asyncio
async def test_database_rejects_invalid_role_permission_value(db_session) -> None:
    role = Role(name=f"raw_sql_role_{uuid4().hex[:8]}", description=None, is_system=False)
    db_session.add(role)
    await db_session.flush()

    with pytest.raises(DBAPIError):
        await db_session.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission) VALUES (:role_id, :permission)"
            ),
            {"role_id": role.id, "permission": "users:read"},
        )
        await db_session.flush()
