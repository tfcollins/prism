"""Run request/response schemas."""

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from prism_api.schemas.log import BootSummary

TagKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
TagValue = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class RunTagOut(BaseModel):
    key: str
    value: str


class RunTagCreate(BaseModel):
    key: TagKey
    value: TagValue


class RunTagUpdate(BaseModel):
    value: TagValue


class CIMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")
    provider: str | None = None
    repository: str | None = None
    workflow: str | None = None
    run_id: str | None = None
    attempt: str | None = None
    job_name: str | None = None
    matrix: dict[str, Any] | None = None
    run_url: str | None = None
    job_url: str | None = None
    collection_errors: list[str] = Field(default_factory=list)


class HardwareMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")
    place: str | None = None
    board: str | None = None
    carrier: str | None = None
    exporters: list[str] = Field(default_factory=list)
    tags: dict[str, str] = Field(default_factory=dict)
    metadata_status: str | None = None
    metadata_error: str | None = None
    collection_errors: list[str] = Field(default_factory=list)


class RunOut(BaseModel):
    id: str
    project_id: str
    name: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    junit_artifact_id: str | None
    tags: list[RunTagOut] = Field(default_factory=list)
    ci: dict[str, Any] | None = None
    hardware: dict[str, Any] | None = None


class CreateRunMetadata(BaseModel):
    project_slug: str
    name: str
    tags: dict[str, str] = Field(default_factory=dict)
    started_at: datetime | None = None
    ci: CIMetadata | None = None
    hardware: HardwareMetadata | None = None


class SuiteSummary(BaseModel):
    id: str
    name: str
    pass_count: int
    fail_count: int
    error_count: int
    skip_count: int
    duration_ms: int


class RunDetail(RunOut):
    project_slug: str | None = None
    calibration_run_id: str | None = None
    calibration_run_name: str | None = None
    suites: list[SuiteSummary] = Field(default_factory=list)
    boot: "BootSummary | None" = None


class SetCalibrationRequest(BaseModel):
    calibration_run_id: str | None = None


class RunListItem(BaseModel):
    id: str
    project_id: str
    name: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    pass_count: int
    fail_count: int
    error_count: int
    skip_count: int
    suite_names: list[str] = Field(default_factory=list)
    tags: list[RunTagOut] = Field(default_factory=list)
    has_figures: bool = False
    has_boot_log: bool = False
    has_terminal_log: bool = False
