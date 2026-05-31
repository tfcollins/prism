"""Global-search response schema."""

from pydantic import BaseModel


class SearchHit(BaseModel):
    kind: str  # "project" | "run" | "case" | "commit"
    title: str
    subtitle: str = ""
    project_slug: str | None = None
    run_id: str | None = None
