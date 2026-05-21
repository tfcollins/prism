"""Parsed boot/dmesg log facts."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from prism_api.models.base import Base, TimestampMixin


class LogReport(Base, TimestampMixin):
    __tablename__ = "log_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source: Mapped[str] = mapped_column(String(512), nullable=False)
    kernel_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    board: Mapped[str | None] = mapped_column(String(255), nullable=True)
    kernel_commit: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    hdl_commit: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_panic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class LogFinding(Base, TimestampMixin):
    __tablename__ = "log_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    log_report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("log_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    line_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(String(1000), nullable=False)
