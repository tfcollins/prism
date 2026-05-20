"""Runs router test — uses a monkeypatched celery task so ingest runs inline."""

import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _login(client: TestClient) -> str:
    r = client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    assert r.status_code == 200
    return client.cookies.get("prism_csrf") or ""


def _seed_project(client: TestClient) -> None:
    r = client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    assert r.status_code == 201


def _sample_archive() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.log", "hello\n")
    return buf.getvalue()


@pytest.fixture
def patch_ingest(monkeypatch, db_session, storage_fixture):
    """Replace the celery delay with an inline call, and provide the same storage to both sides."""
    from prism_api.ingest import IngestInputs, ingest_run
    from prism_api.routers import runs as runs_module

    def fake_enqueue(run_id: str, junit_bytes: bytes, archive_bytes: bytes | None, storage) -> None:
        ingest_run(
            IngestInputs(run_id=run_id, junit_xml=junit_bytes, archive=archive_bytes),
            session=db_session,
            storage=storage,
        )
        db_session.commit()

    monkeypatch.setattr(runs_module, "enqueue_ingest", fake_enqueue)
    return None


def test_upload_run_with_archive(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    _seed_project(client)

    junit = (Path(__file__).parent / "fixtures" / "sample-junit.xml").read_bytes()
    archive = _sample_archive()
    metadata = {"project_slug": "audio", "name": "nightly-42", "tags": {"branch": "main"}}

    resp = client.post(
        "/api/v1/runs",
        files={
            "junit": ("junit.xml", junit, "application/xml"),
            "archive": ("artifacts.zip", archive, "application/zip"),
        },
        data={"metadata": json.dumps(metadata)},
        headers={"X-Prism-Csrf": csrf},
    )
    assert resp.status_code == 201, resp.text
    run = resp.json()
    assert run["name"] == "nightly-42"
    assert run["status"] == "mixed"
    assert {t["key"]: t["value"] for t in run["tags"]} == {"branch": "main"}


def test_upload_requires_auth(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", b"<testsuites/>", "application/xml")},
        data={"metadata": "{}"},
    )
    assert resp.status_code == 401


def test_upload_unknown_project(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    resp = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", b"<testsuites/>", "application/xml")},
        data={"metadata": json.dumps({"project_slug": "nope", "name": "x"})},
        headers={"X-Prism-Csrf": csrf},
    )
    assert resp.status_code == 404


def _upload_min(client: TestClient, csrf: str, name: str) -> str:
    junit = (Path(__file__).parent / "fixtures" / "sample-junit.xml").read_bytes()
    resp = client.post(
        "/api/v1/runs",
        files={"junit": ("junit.xml", junit, "application/xml")},
        data={"metadata": json.dumps({"project_slug": "audio", "name": name})},
        headers={"X-Prism-Csrf": csrf},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_set_and_clear_calibration_run(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    _seed_project(client)
    meas_id = _upload_min(client, csrf, "measurement")
    cal_id = _upload_min(client, csrf, "calibration")

    r = client.patch(
        f"/api/v1/runs/{meas_id}/calibration",
        json={"calibration_run_id": cal_id},
        headers={"X-Prism-Csrf": csrf},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["calibration_run_id"] == cal_id
    assert body["calibration_run_name"] == "calibration"

    # detail endpoint reflects it
    detail = client.get(f"/api/v1/runs/{meas_id}").json()
    assert detail["calibration_run_id"] == cal_id

    # clear it
    r = client.patch(
        f"/api/v1/runs/{meas_id}/calibration",
        json={"calibration_run_id": None},
        headers={"X-Prism-Csrf": csrf},
    )
    assert r.status_code == 200
    assert r.json()["calibration_run_id"] is None


def test_calibration_self_reference_rejected(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    _seed_project(client)
    run_id = _upload_min(client, csrf, "run")
    r = client.patch(
        f"/api/v1/runs/{run_id}/calibration",
        json={"calibration_run_id": run_id},
        headers={"X-Prism-Csrf": csrf},
    )
    assert r.status_code == 400
