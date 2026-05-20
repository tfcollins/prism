from pydantic import BaseModel, Field


class CaseArtifactOut(BaseModel):
    id: str
    kind: str
    filename: str
    size_bytes: int


class MeasurementOut(BaseModel):
    name: str
    value: float
    unit: str | None = None
    spec_min: float | None = None
    spec_max: float | None = None
    in_spec: bool | None = None
    """True/False against the spec limits, or None when no limits are set."""
    margin: float | None = None
    """Distance to the nearest spec limit (positive = inside, negative = violation).

    None when neither limit is set. Same units as ``value``.
    """


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
    measurements: list[MeasurementOut] = Field(default_factory=list)


def measurement_margin(
    value: float, spec_min: float | None, spec_max: float | None
) -> float | None:
    """Signed distance to the nearest spec limit; positive means inside spec.

    With both limits, returns the smaller of the two distances. With one limit,
    returns that distance. None when neither limit is set.
    """
    distances: list[float] = []
    if spec_max is not None:
        distances.append(spec_max - value)
    if spec_min is not None:
        distances.append(value - spec_min)
    if not distances:
        return None
    return min(distances)
