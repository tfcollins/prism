"""Suite + case models."""

import enum
import uuid

from sqlalchemy import Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from prism_api.models.base import Base, TimestampMixin


class CaseStatus(enum.StrEnum):
    PASS = "pass"  # noqa: S105
    FAIL = "fail"
    ERROR = "error"
    SKIP = "skip"


class TestSuite(Base, TimestampMixin):
    __tablename__ = "test_suites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(2048), nullable=False)
    pass_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skip_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class TestCase(Base, TimestampMixin):
    __tablename__ = "test_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    suite_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_suites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    classname: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    name: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[CaseStatus] = mapped_column(Enum(CaseStatus, native_enum=False), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_trace: Mapped[str | None] = mapped_column(Text, nullable=True)


class Measurement(Base, TimestampMixin):
    """A named numeric measurement attached to a test case (e.g. channel power).

    Spec limits are optional; pass/fail and margin are derived from them in the
    response schema rather than stored, so re-speccing a project does not require
    rewriting historical measurement rows.
    """

    __tablename__ = "measurements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    spec_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    spec_max: Mapped[float | None] = mapped_column(Float, nullable=True)
