"""add log_reports and log_findings tables

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "log_reports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("artifact_id", sa.String(length=36), nullable=True),
        sa.Column("source", sa.String(length=512), nullable=False),
        sa.Column("kernel_version", sa.String(length=255), nullable=True),
        sa.Column("board", sa.String(length=255), nullable=True),
        sa.Column("kernel_commit", sa.String(length=64), nullable=True),
        sa.Column("hdl_commit", sa.String(length=64), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("warn_count", sa.Integer(), nullable=False),
        sa.Column("has_panic", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["test_runs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_log_reports_run_id", "log_reports", ["run_id"])
    op.create_index("ix_log_reports_kernel_commit", "log_reports", ["kernel_commit"])
    op.create_index("ix_log_reports_hdl_commit", "log_reports", ["hdl_commit"])
    op.create_table(
        "log_findings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("log_report_id", sa.String(length=36), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=True),
        sa.Column("text", sa.String(length=1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["log_report_id"], ["log_reports.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_log_findings_log_report_id", "log_findings", ["log_report_id"])


def downgrade() -> None:
    op.drop_index("ix_log_findings_log_report_id", table_name="log_findings")
    op.drop_table("log_findings")
    op.drop_index("ix_log_reports_hdl_commit", table_name="log_reports")
    op.drop_index("ix_log_reports_kernel_commit", table_name="log_reports")
    op.drop_index("ix_log_reports_run_id", table_name="log_reports")
    op.drop_table("log_reports")
