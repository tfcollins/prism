"""Matrix router HTTP tests."""

from datetime import UTC, datetime

from prism_api.auth import hash_password
from prism_api.models.project import Project
from prism_api.models.run import RunStatus, RunTag, TestRun
from prism_api.models.suite import TestSuite
from prism_api.repos.users import UserRepo


def _login(client, db_session, settings, *, admin=True):
    email = settings.admin_email if admin and settings.admin_email else "admin@x.com"
    UserRepo(db_session).create(email=email, password_hash=hash_password("pw"))
    db_session.commit()
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "pw"})
    assert r.status_code == 200
    return email


def _seed_cell(db_session):
    p = Project(slug="kuiper-linux", name="Kuiper")
    db_session.add(p)
    db_session.flush()
    run = TestRun(project_id=p.id, name="r", status=RunStatus.PASS, finished_at=datetime.now(UTC))
    db_session.add(run)
    db_session.flush()
    db_session.add_all([
        RunTag(run_id=run.id, key="hw", value="ad9081"),
        RunTag(run_id=run.id, key="platform", value="zcu102"),
        TestSuite(run_id=run.id, name="s", pass_count=5, fail_count=0,
                  error_count=0, skip_count=0, duration_ms=0),
    ])
    db_session.commit()


def test_matrix_read_requires_auth(client):
    assert client.get("/api/v1/matrix?scope=project:kuiper-linux").status_code == 401


def test_matrix_read_returns_grid(client, db_session, settings):
    _login(client, db_session, settings)
    _seed_cell(db_session)
    r = client.get("/api/v1/matrix?scope=project:kuiper-linux")
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == ["ad9081"]
    assert body["cells"]["ad9081|zcu102"]["status"] == "pass"


def test_config_get_returns_defaults(client, db_session, settings):
    _login(client, db_session, settings)
    r = client.get("/api/v1/matrix/config?scope=global")
    assert r.status_code == 200
    assert r.json()["config"]["stale_after_hours"] == 48


def test_config_put_admin_only(client, db_session, settings):
    # Log in as a NON-admin (settings.admin_email differs from this user).
    UserRepo(db_session).create(email="user@x.com", password_hash=hash_password("pw"))
    db_session.commit()
    assert client.post("/api/v1/auth/login",
                       json={"email": "user@x.com", "password": "pw"}).status_code == 200
    csrf = client.cookies.get("prism_csrf")
    r = client.put("/api/v1/matrix/config?scope=global",
                   json={"stale_after_hours": 24}, headers={"X-Prism-Csrf": csrf})
    assert r.status_code == 403


def test_config_put_then_get(client, db_session, settings):
    _login(client, db_session, settings)
    csrf = client.cookies.get("prism_csrf")
    r = client.put("/api/v1/matrix/config?scope=global",
                   json={"stale_after_hours": 24}, headers={"X-Prism-Csrf": csrf})
    assert r.status_code == 200
    got = client.get("/api/v1/matrix/config?scope=global").json()
    assert got["config"]["stale_after_hours"] == 24
