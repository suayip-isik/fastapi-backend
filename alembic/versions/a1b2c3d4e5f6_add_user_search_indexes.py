"""add user search indexes

Revision ID: a1b2c3d4e5f6
Revises: f3a8b1c05d20
Create Date: 2026-04-04 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "d9f3b2e01c47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Users tablosuna arama ve filtre indexleri ekler.

    pg_trgm extension'ı ile GIN trigram indexleri ILIKE '%term%' sorgularının
    sequential scan yerine index scan kullanmasını sağlar. Üç ayrı index,
    PostgreSQL'in bitmap OR scan ile en seçici olanı seçmesine izin verir.
    """
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.execute(
        "CREATE INDEX ix_users_email_trgm ON users USING GIN (email gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_users_username_trgm ON users USING GIN (username gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_users_full_name_trgm ON users USING GIN (full_name gin_trgm_ops)"
    )

    # Filtre sorguları için composite B-tree: yüksek cardinaliteden düşüğe sıralı
    op.create_index("ix_users_filters", "users", ["role", "is_active", "is_verified", "deleted_at"])


def downgrade() -> None:
    """Arama ve filtre indexlerini kaldırır."""
    op.drop_index("ix_users_filters", table_name="users")
    op.execute("DROP INDEX IF EXISTS ix_users_full_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_users_username_trgm")
    op.execute("DROP INDEX IF EXISTS ix_users_email_trgm")
    # pg_trgm extension silinmiyor — başka tablolar kullanıyor olabilir
