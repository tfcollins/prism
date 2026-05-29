import io
import json
import zipfile

import pytest
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
        files={
            "junit": ("j.xml", junit, "application/xml"),
            "archive": ("a.zip", arc.getvalue(), "application/zip"),
        },
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
    _login(client)  # just need auth
    resp = client.get("/api/v1/cases/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


_MEAS_JUNIT = b"""<?xml version="1.0"?><testsuites>
<testsuite name="rf" tests="1" failures="0" time="0.1">
<testcase classname="acpr" name="lower" time="0.05">
<properties>
<property name="channel_power_dBm" value="-10.2"/>
<property name="channel_power_dBm__unit" value="dBm"/>
<property name="channel_power_dBm__max" value="-9.0"/>
</properties>
</testcase>
</testsuite></testsuites>"""


def test_case_detail_includes_measurements(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "rf", "name": "RF"})
    run_id = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", _MEAS_JUNIT, "application/xml")},
        data={"metadata": json.dumps({"project_slug": "rf", "name": "r1"})},
        headers={"X-Prism-Csrf": csrf},
    ).json()["id"]
    detail = client.get(f"/api/v1/runs/{run_id}").json()
    suite_id = detail["suites"][0]["id"]
    case_id = client.get(f"/api/v1/suites/{suite_id}/cases").json()[0]["id"]

    body = client.get(f"/api/v1/cases/{case_id}").json()
    assert len(body["measurements"]) == 1
    m = body["measurements"][0]
    assert m["name"] == "channel_power_dBm"
    assert m["value"] == -10.2
    assert m["unit"] == "dBm"
    assert m["spec_max"] == -9.0
    assert m["spec_min"] is None
    # -10.2 is below the -9.0 ceiling → inside spec, margin = -9.0 - (-10.2) = 1.2
    assert m["in_spec"] is True
    assert m["margin"] == pytest.approx(1.2)
