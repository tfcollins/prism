"""Per-test history / flaky-detection endpoints."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from prism_api.models.project import Project
from prism_api.models.run import RunStatus, TestRun
from prism_api.models.suite import CaseStatus, TestCase, TestSuite

# (run index) -> status for the flaky test; the stable test always passes.
FLAKY = [CaseStatus.PASS, CaseStatus.FAIL, CaseStatus.PASS]


def _seed(db_session: Session) -> None:
    project = Project(slug="p", name="P")
    db_session.add(project)
    db_session.flush()
    base = datetime(2026, 5, 1, tzinfo=UTC)
    for i, flaky_status in enumerate(FLAKY):
        run = TestRun(
            project_id=project.id,
            name=f"run-{i}",
            status=RunStatus.MIXED,
            created_at=base + timedelta(days=i),
        )
        db_session.add(run)
        db_session.flush()
        suite = TestSuite(run_id=run.id, name="s", pass_count=1, fail_count=0, duration_ms=0)
        db_session.add(suite)
        db_session.flush()
        db_session.add(
            TestCase(
                suite_id=suite.id,
                classname="c",
                name="t_flaky",
                status=flaky_status,
                duration_ms=10,
            )
        )
        db_session.add(
            TestCase(
                suite_id=suite.id,
                classname="c",
                name="t_stable",
                status=CaseStatus.PASS,
                duration_ms=20,
            )
        )
    db_session.commit()


def _login(client: TestClient) -> None:
    r = client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    assert r.status_code == 200, r.text


def test_tests_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/projects/p/tests").status_code == 401


def test_tests_aggregate_flaky_first(
    client: TestClient, db_session: Session, seed_admin: None
) -> None:
    _seed(db_session)
    _login(client)
    rows = client.get("/api/v1/projects/p/tests").json()
    by_name = {r["name"]: r for r in rows}

    flaky = by_name["t_flaky"]
    assert flaky["runs"] == 3
    assert flaky["fail_count"] == 1
    assert abs(flaky["fail_rate"] - 1 / 3) < 1e-6
    assert flaky["flaky_score"] == 2  # pass -> fail -> pass
    assert flaky["recent_statuses"] == ["pass", "fail", "pass"]

    stable = by_name["t_stable"]
    assert stable["flaky_score"] == 0
    assert stable["fail_rate"] == 0.0

    # Flakiest sorts first.
    assert rows[0]["name"] == "t_flaky"


def test_test_timeline(client: TestClient, db_session: Session, seed_admin: None) -> None:
    _seed(db_session)
    _login(client)
    tl = client.get(
        "/api/v1/projects/p/tests/history", params={"classname": "c", "name": "t_flaky"}
    ).json()
    assert [p["status"] for p in tl] == ["pass", "fail", "pass"]
    assert [p["run_name"] for p in tl] == ["run-0", "run-1", "run-2"]
