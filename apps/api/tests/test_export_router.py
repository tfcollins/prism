"""Project CSV export: header, a measurement row, and a measurement-less case."""

import csv
import io

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from prism_api.models.project import Project
from prism_api.models.run import RunStatus, TestRun
from prism_api.models.suite import CaseStatus, Measurement, TestCase, TestSuite
from prism_api.repos.export import EXPORT_COLUMNS


def _login(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    assert resp.status_code == 200, resp.text


def _seed(db_session: Session) -> None:
    project = Project(slug="acme", name="Acme")
    db_session.add(project)
    db_session.flush()
    run = TestRun(project_id=project.id, name="run-1", status=RunStatus.PASS)
    db_session.add(run)
    db_session.flush()
    suite = TestSuite(run_id=run.id, name="dsp", duration_ms=0)
    db_session.add(suite)
    db_session.flush()
    measured = TestCase(suite_id=suite.id, classname="t", name="test_gain", status=CaseStatus.PASS)
    bare = TestCase(suite_id=suite.id, classname="t", name="test_smoke", status=CaseStatus.PASS)
    db_session.add_all([measured, bare])
    db_session.flush()
    db_session.add(Measurement(case_id=measured.id, name="gain", value=12.5, unit="dB"))
    db_session.commit()


def test_export_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/projects/acme/export.csv").status_code == 401


def test_export_streams_csv(client: TestClient, db_session: Session, seed_admin: None) -> None:
    _seed(db_session)
    _login(client)
    resp = client.get("/api/v1/projects/acme/export.csv")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")
    assert "acme-export.csv" in resp.headers["content-disposition"]

    rows = list(csv.reader(io.StringIO(resp.text)))
    assert rows[0] == EXPORT_COLUMNS
    body = rows[1:]
    assert len(body) == 2  # one row per case

    by_case = {r[EXPORT_COLUMNS.index("case_name")]: r for r in body}
    gain = by_case["test_gain"]
    assert gain[EXPORT_COLUMNS.index("measurement")] == "gain"
    assert gain[EXPORT_COLUMNS.index("value")] == "12.5"
    assert gain[EXPORT_COLUMNS.index("unit")] == "dB"

    # case without a measurement still appears, with empty measurement cells
    smoke = by_case["test_smoke"]
    assert smoke[EXPORT_COLUMNS.index("measurement")] == ""
    assert smoke[EXPORT_COLUMNS.index("value")] == ""
