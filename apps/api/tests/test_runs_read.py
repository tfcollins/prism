import io
import json
import zipfile

from fastapi.testclient import TestClient


def _login(client: TestClient) -> str:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    return client.cookies.get("prism_csrf") or ""


def _upload(client: TestClient, csrf: str, project_slug: str = "audio", name: str = "r") -> str:
    junit = b"""<?xml version="1.0"?><testsuites>
<testsuite name="dsp" tests="2" failures="1" time="0.1">
<testcase classname="codec" name="ok" time="0.05"/>
<testcase classname="codec" name="bad" time="0.05"><failure message="x">t</failure></testcase>
</testsuite></testsuites>"""
    arc = io.BytesIO()
    with zipfile.ZipFile(arc, "w") as zf:
        zf.writestr("dsp__ok__waveform.csv", "# sample_rate=48000\n0.1\n0.2\n0.3\n")
    resp = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", junit, "application/xml"), "archive": ("a.zip", arc.getvalue(), "application/zip")},
        data={"metadata": json.dumps({"project_slug": project_slug, "name": name, "tags": {"branch": "main"}})},
        headers={"X-Prism-Csrf": csrf},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_list_runs_empty(client: TestClient, seed_admin, patch_ingest) -> None:
    _login(client)
    client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    resp = client.get("/api/v1/runs?project=audio")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_runs_basic(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    _upload(client, csrf, name="r1")
    _upload(client, csrf, name="r2")

    resp = client.get("/api/v1/runs?project=audio")
    assert resp.status_code == 200
    runs = resp.json()
    assert [r["name"] for r in runs] == ["r2", "r1"]  # newest first
    assert runs[0]["pass_count"] == 1
    assert runs[0]["fail_count"] == 1
    # Convention: one JUnit upload == one TestSuiteRun == one <testsuite>
    assert runs[0]["suite_names"] == ["dsp"]


def test_list_runs_exposes_multi_suite_names(
    client: TestClient, seed_admin, patch_ingest
) -> None:
    """When a JUnit happens to contain multiple <testsuite> elements, all of
    their names are surfaced (existing multi-suite uploads still render)."""
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})

    junit = b"""<?xml version="1.0"?><testsuites>
<testsuite name="dsp" tests="1" failures="0" time="0.1">
<testcase classname="c" name="ok" time="0.05"/>
</testsuite>
<testsuite name="api" tests="1" failures="0" time="0.05">
<testcase classname="c" name="happy" time="0.05"/>
</testsuite></testsuites>"""
    resp = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", junit, "application/xml")},
        data={"metadata": json.dumps({"project_slug": "audio", "name": "multi"})},
        headers={"X-Prism-Csrf": csrf},
    )
    assert resp.status_code == 201, resp.text

    listing = client.get("/api/v1/runs?project=audio").json()
    assert len(listing) == 1
    assert sorted(listing[0]["suite_names"]) == ["api", "dsp"]


def test_list_runs_filter_status(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    _upload(client, csrf, name="r-mixed")
    resp = client.get("/api/v1/runs?project=audio&status=mixed")
    assert len(resp.json()) == 1
    resp2 = client.get("/api/v1/runs?project=audio&status=pass")
    assert resp2.json() == []


def test_run_detail(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    run_id = _upload(client, csrf)
    resp = client.get(f"/api/v1/runs/{run_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["id"] == run_id
    assert {s["name"] for s in detail["suites"]} == {"dsp"}
    assert detail["suites"][0]["pass_count"] == 1


def test_run_detail_not_found(client: TestClient, seed_admin) -> None:
    _login(client)
    resp = client.get("/api/v1/runs/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
