"""add admin invite audit actions and permission

Revision ID: c1d2e3f4a5b6
Revises: f9a1b2c3d4e5
Create Date: 2026-04-10 15:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "f9a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """AuditAction enum değerlerini ve admin create permission'ını ekler."""
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'admin_user_created'")
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'admin_invite_resent'")
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission)
        SELECT r.id, 'users:create_admin'
        FROM roles AS r
        WHERE r.name = 'admin'
          AND r.deleted_at IS NULL
          AND NOT EXISTS (
              SELECT 1
              FROM role_permissions rp
              WHERE rp.role_id = r.id
                AND rp.permission = 'users:create_admin'
          )
        """
    )


def downgrade() -> None:
    """PostgreSQL enum değeri silmeyi desteklemez; permission geri alınır."""
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission = 'users:create_admin'
          AND role_id IN (
              SELECT id FROM roles WHERE name = 'admin'
          )
        """
    )
