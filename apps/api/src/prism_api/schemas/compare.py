from pydantic import BaseModel, Field


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


class CompareResponse(BaseModel):
    runs: list[RunHeader]
    cases: list[CaseDiff]
    pass_rate_delta: float | None  # (run[-1] - run[0]) / total, or None if zero divides
