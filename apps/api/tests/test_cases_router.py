import io
import json
import zipfile

from fastapi.testclient import TestClient


def _login(client: TestClient) -> str:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    return client.cookies.get("prism_csrf") or ""


def _bootstrap(client: TestClient, csrf: str) -> str:
    client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    junit = b"""<?xml version="1.0"?><testsuites>
<testsuite name="dsp" tests="1" failures="0" time="0.1">
<testcase classname="codec" name="ok" time="0.05"/>
</testsuite></testsuites>"""
    arc = io.BytesIO()
    with zipfile.ZipFile(arc, "w") as zf:
        zf.writestr("dsp__ok__waveform.csv", "# sample_rate=48000\n0.1\n0.2\n")
    resp = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", junit, "application/xml"), "archive": ("a.zip", arc.getvalue(), "application/zip")},
        data={"metadata": json.dumps({"project_slug": "audio", "name": "r1"})},
        headers={"X-Prism-Csrf": csrf},
    )
    return resp.json()["id"]


def test_suite_cases_list(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    run_id = _bootstrap(client, csrf)
    detail = client.get(f"/api/v1/runs/{run_id}").json()
    suite_id = detail["suites"][0]["id"]
    cases = client.get(f"/api/v1/suites/{suite_id}/cases").json()
    assert [c["name"] for c in cases] == ["ok"]


def test_case_detail(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    run_id = _bootstrap(client, csrf)
    detail = client.get(f"/api/v1/runs/{run_id}").json()
    suite_id = detail["suites"][0]["id"]
    cases = client.get(f"/api/v1/suites/{suite_id}/cases").json()
    case_id = cases[0]["id"]

    resp = client.get(f"/api/v1/cases/{case_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "ok"
    # The attached waveform CSV should be in artifacts
    assert any(a["kind"] == "waveform_csv" for a in body["artifacts"])


def test_case_not_found(client: TestClient, seed_admin) -> None:
    _login(client)  # noqa: just need auth
    resp = client.get("/api/v1/cases/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
