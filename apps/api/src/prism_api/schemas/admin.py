"""Admin-panel response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AccountOut(BaseModel):
    id: str
    email: str
    auth_provider: str
    is_admin: bool
    created_at: datetime


class BackupRunOut(BaseModel):
    timestamp: str
    status: str  # "ok" | "error"
    postgres_bytes: int | None = None
    minio_included: bool = False
    minio_bytes: int | None = None
    cloudsmith: str = "skipped"  # "pushed" | "skipped" | "error"
    keep: int | None = None
    error: str | None = None


class ActivityEventOut(BaseModel):
    action: str
    user_email: str | None = None
    project_id: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ContainerLogsOut(BaseModel):
    service: str
    available: bool
    message: str | None = None
    lines: list[str] = Field(default_factory=list)
