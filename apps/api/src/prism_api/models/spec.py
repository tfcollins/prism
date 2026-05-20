"""Project-level spec definitions (per measurement name)."""

import uuid

from sqlalchemy import Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from prism_api.models.base import Base, TimestampMixin


class SpecDefinition(Base, TimestampMixin):
    """A canonical limit for a measurement name within a project.

    Applied at read time only when a measurement carries no embedded limits, so
    limits frozen into historical runs at ingest always take precedence and
    re-speccing never rewrites past pass/fail.
    """

    __tablename__ = "spec_definitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    measurement_name: Mapped[str] = mapped_column(String(255), nullable=False)
    spec_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    spec_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (
        UniqueConstraint("project_id", "measurement_name", name="uq_spec_project_name"),
    )
