"""Landing/overview response schemas."""

from datetime import datetime

from pydantic import BaseModel


class OverviewStats(BaseModel):
    total_projects: int
    total_runs: int
    total_tests: int  # total test-case executions (sum of suite counts)
    total_failures: int  # failed + errored cases
    pass_rate: float  # 0.0-1.0 over all test executions


class RecentRun(BaseModel):
    id: str
    name: str
    project_slug: str
    project_name: str
    status: str
    created_at: datetime
    pass_count: int
    fail_count: int


class DailyPoint(BaseModel):
    date: str  # YYYY-MM-DD (UTC)
    runs: int
    failures: int


class OverviewResponse(BaseModel):
    stats: OverviewStats
    recent_runs: list[RecentRun]
    daily: list[DailyPoint]
