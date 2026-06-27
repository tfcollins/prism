"""Project model."""

import uuid

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from prism_api.models.base import Base, TimestampMixin


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # When true, ingest computes genalyzer metrics for waveform cases and records
    # them as `genalyzer.*` measurements (a run's `genalyzer` tag overrides this).
    genalyzer_auto: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
