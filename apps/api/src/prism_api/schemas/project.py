"""Project schemas."""

import re

from pydantic import BaseModel, Field, field_validator

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,98}[a-z0-9])?$")


class CreateProjectRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    description: str = ""

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError("slug must be lowercase alphanumeric with internal hyphens")
        return v


class ProjectOut(BaseModel):
    id: str
    slug: str
    name: str
    description: str
    genalyzer_auto: bool = False


class UpdateProjectRequest(BaseModel):
    genalyzer_auto: bool
