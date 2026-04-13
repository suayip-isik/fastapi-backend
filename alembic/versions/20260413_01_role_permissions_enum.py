"""Harden role_permissions.permission with PostgreSQL enum.

Revision ID: 20260413_01
Revises: 68d9fd073c84
Create Date: 2026-04-13 13:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.permissions import Permission

revision: str = "20260413_01"
down_revision: Union[str, None] = "68d9fd073c84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PERMISSION_VALUES: tuple[str, ...] = tuple(permission.value for permission in Permission)
permission_enum = sa.Enum(*PERMISSION_VALUES, name="permissionenum")


def _load_invalid_permissions() -> list[str]:
    bind = op.get_bind()
    existing_permissions = bind.execute(
        sa.text("SELECT DISTINCT permission FROM role_permissions WHERE permission IS NOT NULL")
    ).scalars()
    return sorted({permission for permission in existing_permissions if permission not in PERMISSION_VALUES})


def upgrade() -> None:
    """role_permissions.permission alanını canonical enum ile sınırlar."""
    invalid_permissions = _load_invalid_permissions()
    if invalid_permissions:
        raise RuntimeError(
            "role_permissions tablosunda canonical permission sözlüğü dışında değerler var: "
            f"{', '.join(invalid_permissions)}"
        )

    bind = op.get_bind()
    permission_enum.create(bind, checkfirst=True)
    op.execute(
        """
        ALTER TABLE role_permissions
        ALTER COLUMN permission TYPE permissionenum
        USING permission::permissionenum
        """
    )


def downgrade() -> None:
    """role_permissions.permission alanını tekrar string kolona çevirir."""
    bind = op.get_bind()
    op.execute(
        """
        ALTER TABLE role_permissions
        ALTER COLUMN permission TYPE VARCHAR(100)
        USING permission::text
        """
    )
    permission_enum.drop(bind, checkfirst=True)
