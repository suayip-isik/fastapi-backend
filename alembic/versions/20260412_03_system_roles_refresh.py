"""Document canonical role reset rollout head.

Revision ID: 20260412_03
Revises: 20260411_02
Create Date: 2026-04-12 12:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260412_03"
down_revision: Union[str, None] = "20260411_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Canonical reset operasyonel komutla yapıldığından no-op."""
    pass


def downgrade() -> None:
    """Canonical reset için geri dönüş migration'ı yok."""
    pass
