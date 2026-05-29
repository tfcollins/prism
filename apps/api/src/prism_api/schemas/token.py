"""API-token request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class CreateTokenRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)


class TokenOut(BaseModel):
    id: str
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None = None
    expires_at: datetime | None = None


class TokenCreatedOut(TokenOut):
    # The secret, returned exactly once at creation time.
    token: str
