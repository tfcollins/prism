"""add spec_definitions table

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "spec_definitions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("measurement_name", sa.String(length=255), nullable=False),
        sa.Column("spec_min", sa.Float(), nullable=True),
        sa.Column("spec_max", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "measurement_name", name="uq_spec_project_name"),
    )
    op.create_index("ix_spec_definitions_project_id", "spec_definitions", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_spec_definitions_project_id", table_name="spec_definitions")
    op.drop_table("spec_definitions")
