"""widen test_cases.name + test_cases.classname + test_suites.name to VARCHAR(2048)

Pytest parametrize ids that include large dicts (e.g. an AD936x SFDR
sweep that puts the full param_set into the test name) routinely
exceed 255 bytes after junit serialization, breaking ingest with
StringDataRightTruncation.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("test_cases", "name", type_=sa.String(2048))
    op.alter_column("test_cases", "classname", type_=sa.String(2048))
    op.alter_column("test_suites", "name", type_=sa.String(2048))


def downgrade() -> None:
    op.alter_column("test_suites", "name", type_=sa.String(255))
    op.alter_column("test_cases", "classname", type_=sa.String(255))
    op.alter_column("test_cases", "name", type_=sa.String(255))
