"""add measurements table

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "measurements",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("spec_min", sa.Float(), nullable=True),
        sa.Column("spec_max", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["test_cases.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_measurements_case_id", "measurements", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_measurements_case_id", table_name="measurements")
    op.drop_table("measurements")
