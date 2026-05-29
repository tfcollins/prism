"""Per-test history / flaky-detection response schemas."""

from datetime import datetime

from pydantic import BaseModel


class TestSummary(BaseModel):
    classname: str
    name: str
    runs: int
    pass_count: int
    fail_count: int  # failed + errored
    skip_count: int
    fail_rate: float  # (fail + error) / runs, 0.0-1.0
    flaky_score: int  # pass<->fail transitions across the ordered run history
    last_status: str
    avg_duration_ms: float
    last_duration_ms: int
    recent_statuses: list[str]  # oldest->newest, for a sparkline


class TestTimelinePoint(BaseModel):
    run_id: str
    run_name: str
    created_at: datetime
    status: str
    duration_ms: int
