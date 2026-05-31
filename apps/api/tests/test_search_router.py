"""Global search endpoint: per-kind hits, min-length guard, auth."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from prism_api.models.log import LogReport
from prism_api.models.project import Project
from prism_api.models.run import RunStatus, TestRun
from prism_api.models.suite import CaseStatus, TestCase, TestSuite


def _login(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    assert resp.status_code == 200, resp.text


def _seed(db_session: Session) -> None:
    project = Project(slug="acme", name="Acme Radios")
    db_session.add(project)
    db_session.flush()
    run = TestRun(project_id=project.id, name="nightly-widget", status=RunStatus.MIXED)
    db_session.add(run)
    db_session.flush()
    suite = TestSuite(run_id=run.id, name="dsp", duration_ms=0)
    db_session.add(suite)
    db_session.flush()
    db_session.add(
        TestCase(
            suite_id=suite.id,
            classname="tests.dsp",
            name="test_fft_peak",
            status=CaseStatus.FAIL,
            failure_message="amplitude mismatch",
        )
    )
    db_session.add(
        LogReport(
            run_id=run.id,
            source="boot.log",
            kernel_commit="deadbeefcafe1234",
            hdl_commit="0011223344556677",
        )
    )
    db_session.commit()


def test_search_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/search", params={"q": "acme"}).status_code == 401


def test_search_short_query_returns_empty(client: TestClient, seed_admin: None) -> None:
    _login(client)
    resp = client.get("/api/v1/search", params={"q": "a"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_search_finds_each_kind(client: TestClient, db_session: Session, seed_admin: None) -> None:
    _seed(db_session)
    _login(client)

    def kinds(q: str) -> list[dict[str, str]]:
        resp = client.get("/api/v1/search", params={"q": q})
        assert resp.status_code == 200, resp.text
        return resp.json()

    proj = kinds("acme")
    assert any(h["kind"] == "project" and h["project_slug"] == "acme" for h in proj)

    run = kinds("widget")
    assert any(h["kind"] == "run" and h["title"] == "nightly-widget" for h in run)

    case = kinds("fft")
    assert any(h["kind"] == "case" and h["title"] == "test_fft_peak" for h in case)

    # failure_message is searchable too
    assert any(h["kind"] == "case" for h in kinds("amplitude"))

    commit = kinds("deadbeef")
    assert any(h["kind"] == "commit" and h["title"] == "deadbeefcafe" for h in commit)
