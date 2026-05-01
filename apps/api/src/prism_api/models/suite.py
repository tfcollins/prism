"""Suite + case models."""

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
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
