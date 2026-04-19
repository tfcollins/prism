"""CLI bootstrap test."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from prism_api.cli import bootstrap_admin
from prism_api.config import Settings
from prism_api.models import Base
from prism_api.repos.users import UserRepo


@pytest.fixture
def settings(tmp_path) -> Settings:
    db_path = tmp_path / "test.db"
    return Settings(  # type: ignore[call-arg]
        database_url=f"sqlite:///{db_path}",
        s3_endpoint="x",
        s3_access_key="x",
        s3_secret_key="x",
        s3_bucket="x",
        redis_url="x",
        jwt_secret="s",
        admin_email="boot@x.com",
        admin_password="bootpw",
    )


def test_bootstrap_admin_creates_user(settings: Settings) -> None:
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    bootstrap_admin(settings)
    with sessionmaker(bind=engine)() as s:
        assert UserRepo(s).get_by_email("boot@x.com") is not None


def test_bootstrap_admin_idempotent(settings: Settings) -> None:
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    bootstrap_admin(settings)
    bootstrap_admin(settings)  # second call should be a no-op
    with sessionmaker(bind=engine)() as s:
        assert len(UserRepo(s).list_all()) == 1
