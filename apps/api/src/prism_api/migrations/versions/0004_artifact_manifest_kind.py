"""add nullable manifest_kind column to artifacts

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "artifacts",
        sa.Column("manifest_kind", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("artifacts", "manifest_kind")
