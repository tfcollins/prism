"""Persist optional CI and reserved-hardware provenance.

Revision ID: 0017
Revises: 0016
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    column_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.add_column("test_runs", sa.Column("ci", column_type, nullable=True))
    op.add_column("test_runs", sa.Column("hardware", column_type, nullable=True))


def downgrade() -> None:
    op.drop_column("test_runs", "hardware")
    op.drop_column("test_runs", "ci")
