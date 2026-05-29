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
    # Dispose the engine so the StaticPool's single SQLite connection is closed
    # deterministically. Without this it lingers until GC, and closing it during
    # garbage collection raises "Exception ignored in: <sqlite3.Connection>",
    # which `filterwarnings = error` turns into spurious, order-dependent test
    # failures (PytestUnraisableExceptionWarning) in unrelated tests.
    engine.dispose()


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


@pytest.fixture
def patch_ingest(monkeypatch, db_session, storage_fixture):
    """Replace the celery delay with an inline call, and provide the same storage to both sides."""
    from prism_api.ingest import IngestInputs, ingest_run
    from prism_api.routers import artifacts as artifacts_module
    from prism_api.routers import runs as runs_module

    def fake_enqueue(run_id: str, junit_bytes: bytes, archive_bytes: bytes | None, storage) -> None:
        ingest_run(
            IngestInputs(run_id=run_id, junit_xml=junit_bytes, archive=archive_bytes),
            session=db_session,
            storage=storage,
        )
        db_session.commit()

    monkeypatch.setattr(runs_module, "enqueue_ingest", fake_enqueue)
    monkeypatch.setattr(artifacts_module, "build_storage", lambda s: storage_fixture)
    return None


@pytest.fixture
def storage_fixture(monkeypatch):
    """In-memory S3 for tests that need a storage instance.

    Also monkeypatches `runs_module.build_storage` so the router uses the
    same moto-backed bucket rather than trying to connect to a real S3.
    """
    import boto3
    from moto import mock_aws

    from prism_api.routers import runs as runs_module
    from prism_api.storage import ObjectStorage

    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="prism")
        storage = ObjectStorage(client=client, bucket="prism")
        monkeypatch.setattr(runs_module, "build_storage", lambda s: storage)
        yield storage
