"""User-settings request/response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class UserSettingIn(BaseModel):
    value: dict[str, Any]


class UserSettingOut(BaseModel):
    key: str
    value: dict[str, Any]
    updated_at: datetime
