import json

from fastapi.testclient import TestClient


def _login(client: TestClient) -> str:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    return client.cookies.get("prism_csrf") or ""


def test_audit_records_run_upload_and_spec_edit(
    client: TestClient, seed_admin, patch_ingest
) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "rf", "name": "RF"})

    junit = b'<?xml version="1.0"?><testsuites><testsuite name="s" tests="1" failures="0"><testcase classname="c" name="t"/></testsuite></testsuites>'  # noqa: E501
    client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", junit, "application/xml")},
        data={"metadata": json.dumps({"project_slug": "rf", "name": "r1"})},
        headers={"X-Prism-Csrf": csrf},
    )
    client.put(
        "/api/v1/projects/rf/specs",
        json={"measurement_name": "evm_pct", "spec_max": 5.0},
        headers={"X-Prism-Csrf": csrf},
    )

    events = client.get("/api/v1/projects/rf/audit").json()
    actions = [e["action"] for e in events]
    assert "run.upload" in actions
    assert "spec.upsert" in actions
    # newest first; every event is attributed to the admin user
    assert events[0]["action"] == "spec.upsert"
    assert all(e["user_email"] == "admin@x.com" for e in events)
