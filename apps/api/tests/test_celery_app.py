from prism_api.config import Settings
from prism_api.worker.celery_app import build_celery


def _s() -> Settings:
    return Settings(  # type: ignore[call-arg]
        database_url="sqlite:///:memory:",
        s3_endpoint="x",
        s3_access_key="x",
        s3_secret_key="x",
        s3_bucket="x",
        redis_url="redis://localhost:6379/0",
        jwt_secret="testsecretlongenough",
    )


def test_celery_app_configured_from_settings() -> None:
    app = build_celery(_s())
    assert app.conf.broker_url == "redis://localhost:6379/0"
    assert app.conf.result_backend == "redis://localhost:6379/0"
    assert app.conf.task_serializer == "json"
