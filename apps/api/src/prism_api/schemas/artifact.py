from pydantic import BaseModel


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
    params: dict
