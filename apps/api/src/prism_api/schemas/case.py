from pydantic import BaseModel, Field


class CaseArtifactOut(BaseModel):
    id: str
    kind: str
    filename: str
    size_bytes: int


class CaseDetail(BaseModel):
    id: str
    suite_id: str
    classname: str
    name: str
    status: str
    duration_ms: int
    failure_message: str | None
    failure_trace: str | None
    artifacts: list[CaseArtifactOut] = Field(default_factory=list)
