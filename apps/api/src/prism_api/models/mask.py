"""Spectrum emission mask model.

A mask is a project-level reusable limit line: a list of piecewise segments,
each ``{f_start, f_end, max_dbm}``. Spectra in the project can be overlaid
against a mask and checked for violations.
"""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from prism_api.models.base import Base, TimestampMixin

_JSON = JSONB().with_variant(JSON(), "sqlite")


class SpectrumMask(Base, TimestampMixin):
    __tablename__ = "spectrum_masks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # list[{"f_start": float, "f_end": float, "max_dbm": float}]
    segments: Mapped[list[dict[str, Any]]] = mapped_column(_JSON, nullable=False, default=list)
