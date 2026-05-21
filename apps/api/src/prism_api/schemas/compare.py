from pydantic import BaseModel, Field

from prism_api.schemas.log import BootSummary


class CompareRequest(BaseModel):
    run_ids: list[str] = Field(min_length=2, max_length=10)


class CaseDiff(BaseModel):
    classname: str
    name: str
    suite_name: str
    statuses: list[str | None]  # one entry per requested run, None = case absent in that run
    waveform_artifact_ids: list[str | None] = Field(default_factory=list)
    # one entry per requested run, None = case absent OR no waveform artifact attached


class RunHeader(BaseModel):
    id: str
    name: str
    status: str
    pass_count: int
    fail_count: int


class MeasurementDiff(BaseModel):
    name: str
    unit: str | None = None
    values: list[float | None]  # one per requested run, None = measurement absent in that run
    delta: float | None = None  # last - first when both present, else None


class CompareResponse(BaseModel):
    runs: list[RunHeader]
    cases: list[CaseDiff]
    pass_rate_delta: float | None  # (run[-1] - run[0]) / total, or None if zero divides
    measurement_diffs: list[MeasurementDiff] = Field(default_factory=list)
    boots: list[BootSummary | None] = Field(default_factory=list)
