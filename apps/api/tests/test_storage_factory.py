from unittest.mock import patch

from prism_api.config import Settings
from prism_api.storage import build_storage


def _settings(**overrides) -> Settings:
    base = {
        "database_url": "sqlite:///:memory:",
        "s3_endpoint": "http://minio:9000",
        "s3_access_key": "ak",
        "s3_secret_key": "sk",
        "s3_bucket": "prism",
        "redis_url": "redis://r:6379/0",
        "jwt_secret": "testsecretlongenough",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[call-arg]


def test_build_storage_uses_settings_endpoint_and_creds():
    with patch("prism_api.storage.boto3.client") as mock_client:
        build_storage(_settings())
        kwargs = mock_client.call_args.kwargs
        assert kwargs["endpoint_url"] == "http://minio:9000"
        assert kwargs["aws_access_key_id"] == "ak"
        assert kwargs["aws_secret_access_key"] == "sk"
