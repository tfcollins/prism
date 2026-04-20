"""Runs router test — uses a monkeypatched celery task so ingest runs inline."""
import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _login(client: TestClient) -> None:
    r = client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    assert r.status_code == 200


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
    from prism_api.routers import runs as runs_module

    def fake_enqueue(run_id: str, junit_xml: bytes, archive: bytes | None) -> None:
        from prism_api.ingest import IngestInputs, ingest_run
        ingest_run(
            IngestInputs(run_id=run_id, junit_xml=junit_xml, archive=archive),
            session=db_session,
            storage=storage_fixture,
        )
        db_session.commit()

    monkeypatch.setattr(runs_module, "enqueue_ingest", fake_enqueue)
    return None


def test_upload_run_with_archive(client: TestClient, seed_admin, patch_ingest) -> None:
    _login(client)
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
    )
    assert resp.status_code == 201, resp.text
    run = resp.json()
    assert run["name"] == "nightly-42"
    assert run["status"] == "mixed"
    assert {t["key"]: t["value"] for t in run["tags"]} == {"branch": "main"}


def test_upload_requires_auth(client: TestClient) -> None:
    resp = client.post("/api/v1/runs", files={"junit": ("j.xml", b"<testsuites/>", "application/xml")}, data={"metadata": "{}"})
    assert resp.status_code == 401


def test_upload_unknown_project(client: TestClient, seed_admin, patch_ingest) -> None:
    _login(client)
    resp = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", b"<testsuites/>", "application/xml")},
        data={"metadata": json.dumps({"project_slug": "nope", "name": "x"})},
    )
    assert resp.status_code == 404
