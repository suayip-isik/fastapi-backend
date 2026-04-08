"""roles: drop global unique constraint roles_name_key

Revision ID: 5a3b7c1d9e2f
Revises: 3d1e5fc297hc
Create Date: 2026-04-08 00:00:00.000000

Değişiklikler:
- roles.name kolonundaki global unique constraint (roles_name_key) kaldırıldı
- Soft-delete edilmiş roller ile aynı isimde yeni rol oluşturulabilmesi için
  bu constraint'in kaldırılması gerekiyor
- Aktif satırlar arasındaki uniqueness ix_roles_name_active partial index ile sağlanıyor
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "5a3b7c1d9e2f"
down_revision: Union[str, None] = "3d1e5fc297hc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'roles_name_key' AND conrelid = 'roles'::regclass
            ) THEN
                ALTER TABLE roles DROP CONSTRAINT roles_name_key;
            END IF;
        END $$
    """)


def downgrade() -> None:
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
