import json

from fastapi.testclient import TestClient


def _login(client: TestClient) -> str:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    return client.cookies.get("prism_csrf") or ""


def _junit_no_limits(value: float) -> bytes:
    """A case carrying a measurement value but NO embedded spec limits."""
    return f"""<?xml version="1.0"?><testsuites>
<testsuite name="rf" tests="1" failures="0" time="0.1">
<testcase classname="acpr" name="lower" time="0.05">
<properties>
<property name="evm_pct" value="{value}"/>
<property name="evm_pct__unit" value="%"/>
</properties>
</testcase>
</testsuite></testsuites>""".encode()


def _upload(client: TestClient, csrf: str, name: str, value: float) -> str:
    r = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", _junit_no_limits(value), "application/xml")},
        data={"metadata": json.dumps({"project_slug": "rf", "name": name})},
        headers={"X-Prism-Csrf": csrf},
    )
    return r.json()["id"]


def _case_id(client: TestClient, run_id: str) -> str:
    detail = client.get(f"/api/v1/runs/{run_id}").json()
    suite_id = detail["suites"][0]["id"]
    return client.get(f"/api/v1/suites/{suite_id}/cases").json()[0]["id"]


def test_spec_crud_and_read_time_application(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "rf", "name": "RF"})
    run_id = _upload(client, csrf, "build-1", 3.5)
    case_id = _case_id(client, run_id)

    # No project spec yet → measurement has no limits, in_spec is None.
    m = client.get(f"/api/v1/cases/{case_id}").json()["measurements"][0]
    assert m["in_spec"] is None
    assert m["spec_max"] is None

    # Define a project spec: evm_pct must be ≤ 5%.
    r = client.put(
        "/api/v1/projects/rf/specs",
        json={"measurement_name": "evm_pct", "spec_max": 5.0, "unit": "%"},
        headers={"X-Prism-Csrf": csrf},
    )
    assert r.status_code == 200, r.text

    # Now the same case reads as in-spec against the project limit.
    m = client.get(f"/api/v1/cases/{case_id}").json()["measurements"][0]
    assert m["spec_max"] == 5.0
    assert m["in_spec"] is True

    # List + delete.
    specs = client.get("/api/v1/projects/rf/specs").json()
    assert specs == [
        {"measurement_name": "evm_pct", "spec_min": None, "spec_max": 5.0, "unit": "%"}
    ]
    d = client.delete("/api/v1/projects/rf/specs/evm_pct", headers={"X-Prism-Csrf": csrf})
    assert d.status_code == 204
    assert client.get("/api/v1/projects/rf/specs").json() == []


def test_embedded_spec_wins_over_project_spec(client: TestClient, seed_admin, patch_ingest) -> None:
    """A measurement that carried its own limits at ingest is frozen — the
    project spec must not override it."""
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "rf", "name": "RF"})
    junit = b"""<?xml version="1.0"?><testsuites>
<testsuite name="rf" tests="1" failures="0" time="0.1">
<testcase classname="acpr" name="lower" time="0.05">
<properties>
<property name="evm_pct" value="3.5"/>
<property name="evm_pct__max" value="4.0"/>
</properties>
</testcase>
</testsuite></testsuites>"""
    r = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", junit, "application/xml")},
        data={"metadata": json.dumps({"project_slug": "rf", "name": "b1"})},
        headers={"X-Prism-Csrf": csrf},
    )
    run_id = r.json()["id"]
    case_id = _case_id(client, run_id)

    client.put(
        "/api/v1/projects/rf/specs",
        json={"measurement_name": "evm_pct", "spec_max": 99.0},
        headers={"X-Prism-Csrf": csrf},
    )
    m = client.get(f"/api/v1/cases/{case_id}").json()["measurements"][0]
    assert m["spec_max"] == 4.0  # embedded limit, not the project's 99.0
