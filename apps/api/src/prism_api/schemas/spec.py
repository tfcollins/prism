"""Spec-definition request/response schemas."""

from pydantic import BaseModel


class SpecDefinitionOut(BaseModel):
    measurement_name: str
    spec_min: float | None = None
    spec_max: float | None = None
    unit: str | None = None


class SpecUpsert(BaseModel):
    measurement_name: str
    spec_min: float | None = None
    spec_max: float | None = None
    unit: str | None = None


def resolve_spec(
    spec_min: float | None,
    spec_max: float | None,
    project_min: float | None,
    project_max: float | None,
) -> tuple[float | None, float | None]:
    """Pick effective limits: embedded (frozen at ingest) win; the project spec
    fills in only when the measurement carried no limits at all."""
    if spec_min is None and spec_max is None:
        return project_min, project_max
    return spec_min, spec_max
