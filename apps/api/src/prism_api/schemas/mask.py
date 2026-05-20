from pydantic import BaseModel, Field


class MaskSegment(BaseModel):
    f_start: float
    f_end: float
    max_dbm: float


class MaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    segments: list[MaskSegment] = Field(min_length=1)


class MaskOut(BaseModel):
    id: str
    project_id: str
    name: str
    segments: list[MaskSegment]
