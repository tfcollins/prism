"""Shared test fixtures."""
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from prism_api.auth import hash_password
from prism_api.config import Settings
from prism_api.deps import get_settings_dep, session_dep
from prism_api.main import app
from prism_api.models import Base
from prism_api.repos.users import UserRepo


@pytest.fixture
def settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        database_url="sqlite:///:memory:",
        s3_endpoint="x",
        s3_access_key="x",
        s3_secret_key="x",
        s3_bucket="x",
        redis_url="x",
        jwt_secret="testsecretlongenough",
    )


@pytest.fixture
def db_session(settings: Settings) -> Iterator[Session]:
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session_ = sessionmaker(bind=engine)
    with Session_() as session:
        yield session


@pytest.fixture
def client(settings: Settings, db_session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_settings_dep] = lambda: settings
    app.dependency_overrides[session_dep] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def seed_admin(db_session: Session) -> None:
    UserRepo(db_session).create(email="admin@x.com", password_hash=hash_password("pw"))
    db_session.commit()
