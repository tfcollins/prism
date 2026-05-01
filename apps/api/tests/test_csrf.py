import json

from fastapi.testclient import TestClient


def test_upload_without_csrf_returns_403(client: TestClient, seed_admin, patch_ingest) -> None:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    resp = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", b"<testsuites/>", "application/xml")},
        data={"metadata": json.dumps({"project_slug": "audio", "name": "x"})},
    )
    assert resp.status_code == 403


def test_upload_with_mismatched_csrf_returns_403(
    client: TestClient, seed_admin, patch_ingest
) -> None:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    resp = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", b"<testsuites/>", "application/xml")},
        data={"metadata": json.dumps({"project_slug": "audio", "name": "x"})},
        headers={"X-Prism-Csrf": "wrong-value"},
    )
    assert resp.status_code == 403
