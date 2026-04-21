"""Settings loading tests."""
import pytest

from prism_api.config import Settings


def test_settings_load_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISM_DATABASE_URL", "postgresql+psycopg://x:y@db:5432/z")
    monkeypatch.setenv("PRISM_S3_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("PRISM_S3_ACCESS_KEY", "ak")
    monkeypatch.setenv("PRISM_S3_SECRET_KEY", "sk")
    monkeypatch.setenv("PRISM_S3_BUCKET", "prism")
    monkeypatch.setenv("PRISM_REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("PRISM_JWT_SECRET", "topsecretlongenough")
    s = Settings()
    assert s.database_url.startswith("postgresql+psycopg://")
    assert s.s3_bucket == "prism"
    assert s.jwt_secret == "topsecretlongenough"


def test_settings_admin_bootstrap_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISM_DATABASE_URL", "postgresql+psycopg://x:y@db:5432/z")
    monkeypatch.setenv("PRISM_S3_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("PRISM_S3_ACCESS_KEY", "ak")
    monkeypatch.setenv("PRISM_S3_SECRET_KEY", "sk")
    monkeypatch.setenv("PRISM_S3_BUCKET", "prism")
    monkeypatch.setenv("PRISM_REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("PRISM_JWT_SECRET", "topsecretlongenough")
    monkeypatch.delenv("PRISM_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("PRISM_ADMIN_PASSWORD", raising=False)
    s = Settings()
    assert s.admin_email is None
    assert s.admin_password is None
