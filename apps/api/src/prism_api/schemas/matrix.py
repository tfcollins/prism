"""Matrix dashboard request/response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class MatrixCell(BaseModel):
    status: str  # RunStatus value: pass/fail/mixed/error
    run_id: str
    passed: int
    total: int
    finished_at: datetime | None
    age_seconds: int
    stale: bool


class MatrixResponse(BaseModel):
    scope: str
    generated_at: datetime
    row_key: str
    col_key: str
    rows: list[str]
    cols: list[str]
    boot_files: list[str]
    stale_after_hours: int
    summary: dict[str, int]
    unplaced_runs: int
    cells: dict[str, MatrixCell]


class MatrixConfigBody(BaseModel):
    row_key: str = "hw"
    col_key: str = "platform"
    filter_key: str = "boot_file"
    curated_rows: list[str] = []
    curated_cols: list[str] = []
    stale_after_hours: int = 48
    refresh_seconds: int = 30
    rotate_filters: list[str] = []


class MatrixConfigOut(BaseModel):
    scope: str
    config: dict[str, Any]
