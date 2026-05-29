"""App configuration via pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from prism_api.parsers.logs import (
    DEFAULT_FINDINGS_CAP,
    DEFAULT_HDL_PATTERN,
    DEFAULT_KERNEL_PATTERN,
)


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
    # LDAP (search + bind). When disabled, only local password auth is used.
    ldap_enabled: bool = False
    ldap_server: str | None = None  # e.g. ldap://dir.example.com:389 or ldaps://...
    ldap_bind_dn: str | None = None  # service account for the search; None = anonymous
    ldap_bind_password: str | None = None
    ldap_user_base_dn: str | None = None  # e.g. ou=people,dc=example,dc=com
    ldap_user_filter: str = "(mail={email})"  # supports {email} and {username}
    ldap_email_attribute: str = "mail"
    ldap_start_tls: bool = False
    ldap_timeout: int = 10
    log_kernel_commit_pattern: str = DEFAULT_KERNEL_PATTERN
    log_hdl_commit_pattern: str = DEFAULT_HDL_PATTERN
    log_findings_cap: int = DEFAULT_FINDINGS_CAP
    kernel_repo_url: str | None = None
    hdl_repo_url: str | None = None

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_not_placeholder(cls, v: str) -> str:
        if len(v) < 16:
            raise ValueError("PRISM_JWT_SECRET must be at least 16 characters")
        if v in {"replace-with-a-long-random-string", "change-me-in-prod"}:
            raise ValueError(
                "PRISM_JWT_SECRET appears to be an example placeholder; set a real secret"
            )
        return v

    @model_validator(mode="after")
    def _ldap_requires_server_and_base(self) -> "Settings":
        if self.ldap_enabled and not (self.ldap_server and self.ldap_user_base_dn):
            raise ValueError(
                "PRISM_LDAP_ENABLED requires PRISM_LDAP_SERVER and PRISM_LDAP_USER_BASE_DN"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
