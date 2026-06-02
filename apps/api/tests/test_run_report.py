import io
import json

from fastapi.testclient import TestClient
from pypdf import PdfReader


def _pdf_text(content: bytes) -> str:
    """Extract the rendered text from a generated PDF (asserts content, not just bytes)."""
    reader = PdfReader(io.BytesIO(content))
    return "\n".join(page.extract_text() for page in reader.pages)


def _login(client: TestClient) -> str:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    return client.cookies.get("prism_csrf") or ""


def _junit() -> bytes:
    return b"""<?xml version="1.0"?><testsuites>
<testsuite name="rf" tests="1" failures="0" time="0.1">
<testcase classname="acpr" name="lower" time="0.05">
<properties>
<property name="channel_power_dBm" value="-10.5"/>
<property name="channel_power_dBm__unit" value="dBm"/>
<property name="channel_power_dBm__max" value="-9.0"/>
</properties>
</testcase>
</testsuite></testsuites>"""


def test_run_report_pdf(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "rf", "name": "RF"})
    r = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", _junit(), "application/xml")},
        data={
            "metadata": json.dumps({"project_slug": "rf", "name": "build-1", "tags": {"dut": "A"}})
        },
        headers={"X-Prism-Csrf": csrf},
    )
    run_id = r.json()["id"]

    resp = client.get(f"/api/v1/runs/{run_id}/report.pdf")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"
    assert "attachment" in resp.headers["content-disposition"]

    # The report must actually render the run's content, not be a blank page.
    text = _pdf_text(resp.content)
    assert "Compliance report" in text
    assert "build-1" in text  # run name
    assert "channel_power_dBm" in text  # measurement name from the JUnit
    assert "-10.5" in text  # its value
    assert "PASS" in text  # in-spec result (value -10.5 <= max -9.0)


def test_run_report_unknown_run_404(client: TestClient, seed_admin) -> None:
    _login(client)
    assert client.get("/api/v1/runs/nope/report.pdf").status_code == 404
