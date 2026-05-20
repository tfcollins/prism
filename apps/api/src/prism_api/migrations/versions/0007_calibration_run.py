"""add calibration_run_id to test_runs

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "test_runs",
        sa.Column("calibration_run_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_test_runs_calibration_run",
        "test_runs",
        "test_runs",
        ["calibration_run_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_test_runs_calibration_run", "test_runs", type_="foreignkey")
    op.drop_column("test_runs", "calibration_run_id")
