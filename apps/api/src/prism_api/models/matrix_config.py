"""Shared matrix-dashboard config, keyed by scope ('global' or 'project:<slug>')."""

import uuid
from typing import Any

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from prism_api.models.base import Base, TimestampMixin

_JSON = JSONB().with_variant(JSON(), "sqlite")


class MatrixConfig(Base, TimestampMixin):
    __tablename__ = "matrix_config"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scope: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False, default=dict)

    __table_args__ = (UniqueConstraint("scope", name="uq_matrix_config_scope"),)
