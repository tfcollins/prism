"""App configuration via pydantic-settings."""
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings. All vars prefixed with PRISM_."""

    model_config = SettingsConfigDict(env_prefix="PRISM_", case_sensitive=False)

    database_url: str
    s3_endpoint: str
    s3_public_endpoint: str | None = None
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str
    redis_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_ttl_minutes: int = Field(default=60 * 24)
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    admin_email: str | None = None
    admin_password: str | None = None

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_not_placeholder(cls, v: str) -> str:
        if len(v) < 16:
            raise ValueError("PRISM_JWT_SECRET must be at least 16 characters")
        if v in {"replace-with-a-long-random-string", "change-me-in-prod"}:
            raise ValueError("PRISM_JWT_SECRET appears to be an example placeholder; set a real secret")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
