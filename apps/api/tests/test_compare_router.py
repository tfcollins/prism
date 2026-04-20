import io
import json
import zipfile

from fastapi.testclient import TestClient


def _login(client: TestClient) -> str:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    return client.cookies.get("prism_csrf") or ""


def _upload(client: TestClient, csrf: str, name: str, junit_xml: bytes) -> str:
    arc = io.BytesIO()
    with zipfile.ZipFile(arc, "w") as zf:
        zf.writestr("readme.log", "ctx\n")
    resp = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", junit_xml, "application/xml"), "archive": ("a.zip", arc.getvalue(), "application/zip")},
        data={"metadata": json.dumps({"project_slug": "audio", "name": name})},
        headers={"X-Prism-Csrf": csrf},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


_BASE_JUNIT = b"""<?xml version="1.0"?><testsuites>
<testsuite name="dsp" tests="2" failures="0" time="0.1">
<testcase classname="codec" name="ok" time="0.05"/>
<testcase classname="codec" name="other" time="0.05"/>
</testsuite></testsuites>"""

_FAIL_ON_OTHER = b"""<?xml version="1.0"?><testsuites>
<testsuite name="dsp" tests="2" failures="1" time="0.1">
<testcase classname="codec" name="ok" time="0.05"/>
<testcase classname="codec" name="other" time="0.05"><failure message="x">t</failure></testcase>
</testsuite></testsuites>"""


def test_compare_two_runs(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    a = _upload(client, csrf, "a", _BASE_JUNIT)
    b = _upload(client, csrf, "b", _FAIL_ON_OTHER)

    resp = client.post(
        "/api/v1/compare",
        json={"run_ids": [a, b]},
        headers={"X-Prism-Csrf": csrf},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [r["id"] for r in body["runs"]] == [a, b]
    statuses = {(c["suite_name"], c["name"]): c["statuses"] for c in body["cases"]}
    assert statuses[("dsp", "ok")] == ["pass", "pass"]
    assert statuses[("dsp", "other")] == ["pass", "fail"]


def test_compare_rejects_single_run(client: TestClient, seed_admin) -> None:
    csrf = _login(client)
    resp = client.post(
        "/api/v1/compare",
        json={"run_ids": ["00000000-0000-0000-0000-000000000000"]},
        headers={"X-Prism-Csrf": csrf},
    )
    assert resp.status_code == 422


def test_compare_unknown_run_404(client: TestClient, seed_admin) -> None:
    csrf = _login(client)
    resp = client.post(
        "/api/v1/compare",
        json={"run_ids": ["00000000-0000-0000-0000-000000000000", "11111111-1111-1111-1111-111111111111"]},
        headers={"X-Prism-Csrf": csrf},
    )
    assert resp.status_code == 404
