"""Admin panel router: access control + accounts/activity/backups/logs."""

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from prism_api import auth as auth_module
from prism_api.config import Settings
from prism_api.deps import get_settings_dep, session_dep
from prism_api.main import app
from prism_api.repos.users import UserRepo

ADMIN_EMAIL = "admin@x.com"


def _settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        database_url="sqlite:///:memory:",
        s3_endpoint="x",
        s3_access_key="x",
        s3_secret_key="x",
        s3_bucket="x",
        redis_url="x",
        jwt_secret="testsecretlongenough",
        admin_email=ADMIN_EMAIL,
        # Point at a path that doesn't exist so the container-logs viewer is
        # deterministically "unavailable" in tests (never touches a real socket).
        docker_socket="/nonexistent/docker.sock",
    )


@pytest.fixture
def admin_settings() -> Settings:
    return _settings()


@pytest.fixture
def client_for(admin_settings: Settings, db_session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_settings_dep] = lambda: admin_settings
    app.dependency_overrides[session_dep] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _seed_and_login(client: TestClient, db_session: Session, email: str) -> None:
    UserRepo(db_session).create(email=email, password_hash=auth_module.hash_password("pw"))
    db_session.commit()
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "pw"})
    assert resp.status_code == 200, resp.text


def test_admin_endpoints_require_authentication(client_for: TestClient) -> None:
    assert client_for.get("/api/v1/admin/accounts").status_code == 401


def test_non_admin_is_forbidden(client_for: TestClient, db_session: Session) -> None:
    _seed_and_login(client_for, db_session, "someone@x.com")
    assert client_for.get("/api/v1/admin/accounts").status_code == 403


def test_admin_lists_accounts(client_for: TestClient, db_session: Session) -> None:
    _seed_and_login(client_for, db_session, ADMIN_EMAIL)
    resp = client_for.get("/api/v1/admin/accounts")
    assert resp.status_code == 200
    accounts = resp.json()
    admin = next(a for a in accounts if a["email"] == ADMIN_EMAIL)
    assert admin["is_admin"] is True
    assert admin["auth_provider"] == "local"


def test_admin_activity_includes_login(client_for: TestClient, db_session: Session) -> None:
    _seed_and_login(client_for, db_session, ADMIN_EMAIL)
    resp = client_for.get("/api/v1/admin/activity")
    assert resp.status_code == 200
    actions = {e["action"] for e in resp.json()}
    assert "auth.login" in actions


def test_admin_backups_reads_manifests(
    client_for: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = {
        "timestamp": "20260529T010000Z",
        "status": "ok",
        "postgres_bytes": 1234,
        "minio_included": True,
        "minio_bytes": 5678,
        "cloudsmith": "skipped",
        "keep": 7,
        "error": None,
    }

    class _FakeStorage:
        def list_prefix(self, prefix: str, *, limit: int = 1000) -> list[str]:
            return [f"{prefix}20260529T010000Z.json"]

        def get_bytes(self, key: str) -> bytes:
            return json.dumps(manifest).encode()

    monkeypatch.setattr("prism_api.routers.admin.build_storage", lambda s: _FakeStorage())
    _seed_and_login(client_for, db_session, ADMIN_EMAIL)
    resp = client_for.get("/api/v1/admin/backups")
    assert resp.status_code == 200
    runs = resp.json()
    assert runs[0]["timestamp"] == "20260529T010000Z"
    assert runs[0]["status"] == "ok"
    assert runs[0]["postgres_bytes"] == 1234


def test_admin_logs_graceful_when_socket_absent(
    client_for: TestClient, db_session: Session
) -> None:
    _seed_and_login(client_for, db_session, ADMIN_EMAIL)
    resp = client_for.get("/api/v1/admin/logs", params={"service": "api"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is False
    assert body["service"] == "api"


def test_admin_logs_rejects_unknown_service(client_for: TestClient, db_session: Session) -> None:
    _seed_and_login(client_for, db_session, ADMIN_EMAIL)
    resp = client_for.get("/api/v1/admin/logs", params={"service": "evil"})
    assert resp.status_code == 200
    assert resp.json()["available"] is False
