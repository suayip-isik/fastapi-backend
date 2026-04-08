"""roles: partial unique index on name for active rows

Revision ID: 3d1e5fc297hc
Revises: 2c0d4eb186gb
Create Date: 2026-04-08 00:00:00.000000

Değişiklikler:
- roles.name global unique kısıtı kaldırıldı
- Yalnızca aktif (deleted_at IS NULL) satırlar arasında benzersizliği
  zorunlu kılan partial unique index eklendi
- Böylece silinen rol adıyla yeni rol oluşturulabilir
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "3d1e5fc297hc"
down_revision: Union[str, None] = "2c0d4eb186gb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ix_roles_name unique index'ini kaldır
    op.drop_index("ix_roles_name", table_name="roles")
    # create_table'daki unique=True'dan gelen column-level constraint'i kaldır
    op.drop_constraint("roles_name_key", "roles", type_="unique")
    # Yalnızca aktif (deleted_at IS NULL) satırlar arasında unique zorunluluğu
    op.create_index(
        "ix_roles_name_active",
        "roles",
        ["name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_roles_name_active", table_name="roles")
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'roles_name_key' AND conrelid = 'roles'::regclass
            ) THEN
                ALTER TABLE roles ADD CONSTRAINT roles_name_key UNIQUE (name);
            END IF;
        END $$
    """)
