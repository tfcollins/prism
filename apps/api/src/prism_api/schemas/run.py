"""Run request/response schemas."""
from datetime import datetime

from pydantic import BaseModel, Field


class RunTagOut(BaseModel):
    key: str
    value: str


class RunOut(BaseModel):
    id: str
    project_id: str
    name: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    junit_artifact_id: str | None
    tags: list[RunTagOut] = Field(default_factory=list)


class CreateRunMetadata(BaseModel):
    project_slug: str
    name: str
    tags: dict[str, str] = Field(default_factory=dict)
    started_at: datetime | None = None
