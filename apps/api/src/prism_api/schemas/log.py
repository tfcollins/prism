"""Log-report response schemas."""

from pydantic import BaseModel, Field


def commit_url(repo_base: str | None, commit: str | None) -> str | None:
    if not repo_base or not commit:
        return None
    return f"{repo_base.rstrip('/')}/commit/{commit}"


class FindingOut(BaseModel):
    severity: str
    line_no: int | None = None
    text: str


class LogReportOut(BaseModel):
    source: str
    kernel_version: str | None = None
    board: str | None = None
    kernel_commit: str | None = None
    hdl_commit: str | None = None
    kernel_commit_url: str | None = None
    hdl_commit_url: str | None = None
    error_count: int
    warn_count: int
    has_panic: bool
    findings: list[FindingOut] = Field(default_factory=list)


class BootSummary(BaseModel):
    kernel_version: str | None = None
    board: str | None = None
    kernel_commit: str | None = None
    hdl_commit: str | None = None
    kernel_commit_url: str | None = None
    hdl_commit_url: str | None = None
    error_count: int = 0
    warn_count: int = 0
    has_panic: bool = False
    shared_kernel_count: int = 0
    shared_hdl_count: int = 0


class CommitCount(BaseModel):
    commit: str
    run_count: int
