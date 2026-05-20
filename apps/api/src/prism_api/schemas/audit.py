"""Audit-event response schema."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditEventOut(BaseModel):
    action: str
    user_email: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
