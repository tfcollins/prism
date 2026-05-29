# apps/api/tests/test_config_log.py
from prism_api.config import Settings


def test_log_settings_defaults() -> None:
    s = Settings(  # type: ignore[call-arg]
        database_url="x",
        s3_endpoint="x",
        s3_access_key="x",
        s3_secret_key="x",
        s3_bucket="x",
        redis_url="x",
        jwt_secret="testsecretlongenough",
    )
    assert s.log_findings_cap == 200
    assert "Linux version" in s.log_kernel_commit_pattern
    assert s.kernel_repo_url is None and s.hdl_repo_url is None
