"""Overview/landing endpoint: stats, recent runs, daily series."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from prism_api.models.project import Project
from prism_api.models.run import RunStatus, TestRun
from prism_api.models.suite import TestSuite


def _seed(db_session: Session) -> None:
    project = Project(slug="p", name="Proj")
    db_session.add(project)
    db_session.flush()
    run = TestRun(
        project_id=project.id,
        name="nightly-1",
        status=RunStatus.MIXED,
        started_at=datetime.now(UTC),
    )
    db_session.add(run)
    db_session.flush()
    db_session.add(
        TestSuite(
            run_id=run.id,
            name="dsp",
            pass_count=3,
            fail_count=1,
            error_count=0,
            skip_count=0,
            duration_ms=10,
        )
    )
    db_session.commit()


def _login(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    assert resp.status_code == 200, resp.text


def test_overview_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/overview").status_code == 401


def test_overview_returns_stats_recent_and_daily(
    client: TestClient, db_session: Session, seed_admin: None
) -> None:
    _seed(db_session)
    _login(client)
    resp = client.get("/api/v1/overview")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    stats = body["stats"]
    assert stats["total_projects"] == 1
    assert stats["total_runs"] == 1
    assert stats["total_tests"] == 4  # 3 pass + 1 fail
    assert stats["total_failures"] == 1
    assert stats["pass_rate"] == 0.75

    assert len(body["recent_runs"]) == 1
    rr = body["recent_runs"][0]
    assert rr["project_slug"] == "p"
    assert rr["name"] == "nightly-1"
    assert rr["fail_count"] == 1

    # 30 daily buckets; today should show 1 run and 1 failure.
    assert len(body["daily"]) == 30
    today = datetime.now(UTC).date().isoformat()
    today_point = next(p for p in body["daily"] if p["date"] == today)
    assert today_point["runs"] == 1
    assert today_point["failures"] == 1


def test_overview_empty_instance(client: TestClient, seed_admin: None) -> None:
    _login(client)
    body = client.get("/api/v1/overview").json()
    assert body["stats"]["total_runs"] == 0
    assert body["stats"]["pass_rate"] == 0.0
    assert body["recent_runs"] == []
    assert len(body["daily"]) == 30
