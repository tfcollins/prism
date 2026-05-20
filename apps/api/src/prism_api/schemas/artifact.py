from typing import Any

from pydantic import BaseModel, Field


class ArtifactOut(BaseModel):
    id: str
    owner_type: str
    owner_id: str
    kind: str
    filename: str
    size_bytes: int
    content_hash: str


class WaveformResponse(BaseModel):
    samples: list[float]
    sample_rate: int | None
    stride: int
    total_samples: int


class FFTResponse(BaseModel):
    frequencies: list[float]
    magnitudes: list[float]
    sample_rate: float
    params: dict[str, str | int | float]


class SpectrumResponse(BaseModel):
    frequencies: list[float]
    powers: list[float]
    unit: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SpectrogramResponse(BaseModel):
    frequencies: list[float]
    times: list[float]
    powers: list[list[float]]  # row per time frame, column per frequency bin
    unit: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChannelMetricsResponse(BaseModel):
    channel_power_dbm: float | None
    acpr_lower_dbc: float | None
    acpr_upper_dbc: float | None
    obw_hz: float | None
    channel_band: tuple[float, float]
    lower_band: tuple[float, float] | None
    upper_band: tuple[float, float] | None


class SpurOut(BaseModel):
    frequency: float
    power: float


class SpursResponse(BaseModel):
    margin_db: float
    noise_floor_dbm: float
    spurs: list[SpurOut] = Field(default_factory=list)
