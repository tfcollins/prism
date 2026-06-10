"""add matrix_config table

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "matrix_config",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("scope", sa.String(length=255), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("scope", name="uq_matrix_config_scope"),
    )


def downgrade() -> None:
    op.drop_table("matrix_config")
