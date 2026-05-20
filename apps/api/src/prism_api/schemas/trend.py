from datetime import datetime

from pydantic import BaseModel, Field


class TrendPoint(BaseModel):
    run_id: str
    run_name: str
    created_at: datetime
    case_id: str
    case_name: str
    value: float
    unit: str | None = None
    spec_min: float | None = None
    spec_max: float | None = None
    in_spec: bool | None = None
    margin: float | None = None
    tags: dict[str, str] = Field(default_factory=dict)


class TrendResponse(BaseModel):
    measurement_name: str
    points: list[TrendPoint] = Field(default_factory=list)


class RegressionEvent(BaseModel):
    measurement_name: str
    run_id: str
    run_name: str
    created_at: datetime
    value: float
    unit: str | None = None
    previous_value: float | None = None
    kind: str  # "crossed_out" (was in spec, now out) | "still_out" (consecutive failures)


class RegressionsResponse(BaseModel):
    events: list[RegressionEvent] = Field(default_factory=list)
