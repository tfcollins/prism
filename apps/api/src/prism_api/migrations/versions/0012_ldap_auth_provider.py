"""add auth_provider to users and make password_hash nullable

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # batch_alter_table keeps this portable to SQLite (column ALTER is emulated
    # via table copy there); on Postgres it issues plain ALTER TABLE statements.
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column(
                "auth_provider",
                sa.String(length=16),
                nullable=False,
                server_default="local",
            )
        )
        batch.alter_column(
            "password_hash",
            existing_type=sa.String(length=255),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "password_hash",
            existing_type=sa.String(length=255),
            nullable=False,
        )
        batch.drop_column("auth_provider")
