"""Saved-view request/response schemas."""

from typing import Any

from pydantic import BaseModel, Field


class SavedViewOut(BaseModel):
    name: str
    config: dict[str, Any] = Field(default_factory=dict)


class SavedViewUpsert(BaseModel):
    name: str
    config: dict[str, Any] = Field(default_factory=dict)
