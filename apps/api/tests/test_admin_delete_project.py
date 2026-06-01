"""Project deletion: cascading row removal + content-addressed blob GC, and the
admin DELETE endpoint (auth, audit, 404)."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from prism_api import auth as auth_module
from prism_api.config import Settings
from prism_api.deps import get_settings_dep, session_dep
from prism_api.main import app
from prism_api.models.artifact import Artifact, ArtifactKind
from prism_api.models.audit import AuditEvent
from prism_api.models.mask import SpectrumMask
from prism_api.models.project import Project
from prism_api.models.run import RunStatus, TestRun
from prism_api.models.spec import SpecDefinition
from prism_api.models.suite import CaseStatus, TestCase, TestSuite
from prism_api.models.view import SavedView
from prism_api.repos.users import UserRepo
from prism_api.services.retention import delete_project

ADMIN_EMAIL = "admin@x.com"


class FakeStorage:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete(self, key: str) -> None:
        self.deleted.append(key)


def _project_with_run(db_session: Session, slug: str) -> tuple[str, str, str]:
    """Create a project with one run/suite/case. Returns (project_id, run_id, case_id)."""
    project = Project(slug=slug, name=slug.upper())
    db_session.add(project)
    db_session.flush()
    run = TestRun(project_id=project.id, name=f"{slug}-run", status=RunStatus.PASS)
    db_session.add(run)
    db_session.flush()
    suite = TestSuite(run_id=run.id, name="s", duration_ms=0)
    db_session.add(suite)
    db_session.flush()
    case = TestCase(suite_id=suite.id, classname="c", name="t", status=CaseStatus.PASS)
    db_session.add(case)
    db_session.flush()
    return project.id, run.id, case.id


def _art(db_session: Session, owner_type: str, owner_id: str, key: str) -> None:
    db_session.add(
        Artifact(
            owner_type=owner_type,
            owner_id=owner_id,
            kind=ArtifactKind.OTHER_BINARY,
            filename="f",
            size_bytes=1,
            content_hash="h",
            storage_key=key,
        )
    )


# --- service ---------------------------------------------------------------


def test_delete_project_removes_runs_scoped_rows_and_orphan_blob(db_session: Session) -> None:
    target_id, target_run, target_case = _project_with_run(db_session, "target")
    other_id, other_run, _ = _project_with_run(db_session, "keep")

    # "shared" lives in both projects (content-addressed); "unique" only in target.
    _art(db_session, "run", target_run, "shared")
    _art(db_session, "case", target_case, "unique")
    _art(db_session, "run", other_run, "shared")

    # project-scoped extras that must also be removed
    db_session.add(SpecDefinition(project_id=target_id, measurement_name="gain", spec_max=10))
    db_session.add(SavedView(project_id=target_id, name="v", config={}))
    db_session.add(SpectrumMask(project_id=target_id, name="m", segments=[]))
    db_session.commit()

    storage = FakeStorage()
    stats = delete_project(db_session, storage, project_id=target_id)  # type: ignore[arg-type]

    assert stats == {"runs": 1, "artifacts": 2, "blobs": 1}
    # target gone, other project intact
    assert db_session.get(Project, target_id) is None
    assert db_session.get(TestRun, target_run) is None
    assert db_session.get(Project, other_id) is not None
    assert db_session.get(TestRun, other_run) is not None
    # only the unique blob was GC'd; "shared" is still referenced by the kept run
    assert storage.deleted == ["unique"]
    # project-scoped rows are gone
    assert db_session.query(SpecDefinition).count() == 0
    assert db_session.query(SavedView).count() == 0
    assert db_session.query(SpectrumMask).count() == 0


def test_delete_empty_project(db_session: Session) -> None:
    project = Project(slug="empty", name="Empty")
    db_session.add(project)
    db_session.commit()
    stats = delete_project(db_session, FakeStorage(), project_id=project.id)  # type: ignore[arg-type]
    assert stats == {"runs": 0, "artifacts": 0, "blobs": 0}
    assert db_session.get(Project, project.id) is None


# --- router ----------------------------------------------------------------


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
        docker_socket="/nonexistent/docker.sock",
    )


@pytest.fixture
def client_for(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    settings = _settings()
    app.dependency_overrides[get_settings_dep] = lambda: settings
    app.dependency_overrides[session_dep] = lambda: db_session
    # Endpoint builds storage directly; swap in a fake so no S3 is touched.
    monkeypatch.setattr("prism_api.routers.admin.build_storage", lambda _s: FakeStorage())
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _login(client: TestClient, db_session: Session, email: str) -> None:
    UserRepo(db_session).create(email=email, password_hash=auth_module.hash_password("pw"))
    db_session.commit()
    assert (
        client.post("/api/v1/auth/login", json={"email": email, "password": "pw"}).status_code
        == 200
    )


def test_delete_requires_admin(client_for: TestClient, db_session: Session) -> None:
    _project_with_run(db_session, "p")
    db_session.commit()
    assert client_for.delete("/api/v1/admin/projects/p").status_code == 401
    _login(client_for, db_session, "nobody@x.com")  # non-admin
    assert client_for.delete("/api/v1/admin/projects/p").status_code == 403


def test_admin_lists_projects_with_run_counts(client_for: TestClient, db_session: Session) -> None:
    _project_with_run(db_session, "alpha")
    db_session.commit()
    _login(client_for, db_session, ADMIN_EMAIL)
    rows = client_for.get("/api/v1/admin/projects").json()
    alpha = next(r for r in rows if r["slug"] == "alpha")
    assert alpha["run_count"] == 1


def test_admin_deletes_project(client_for: TestClient, db_session: Session) -> None:
    pid, run_id, case_id = _project_with_run(db_session, "doomed")
    _art(db_session, "case", case_id, "blob-1")
    db_session.commit()
    _login(client_for, db_session, ADMIN_EMAIL)

    resp = client_for.delete("/api/v1/admin/projects/doomed")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {"slug": "doomed", "runs": 1, "artifacts": 1, "blobs": 1}

    assert db_session.get(Project, pid) is None
    assert db_session.get(TestRun, run_id) is None
    # deletion recorded in the audit log (survives the project row)
    events = db_session.query(AuditEvent).filter(AuditEvent.action == "project.delete").all()
    assert len(events) == 1
    assert events[0].project_id == pid
    # 404 on a second delete
    assert client_for.delete("/api/v1/admin/projects/doomed").status_code == 404
