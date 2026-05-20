"""Saved dashboard views (named filter sets) per project."""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from prism_api.models.base import Base, TimestampMixin

_JSON = JSONB().with_variant(JSON(), "sqlite")


class SavedView(Base, TimestampMixin):
    __tablename__ = "saved_views"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False, default=dict)

    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_view_project_name"),)
