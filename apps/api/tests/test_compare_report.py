"""Multi-run comparison PDF: endpoint (auth, validation) + rendered content."""

import io
import json
import uuid

from fastapi.testclient import TestClient
from pypdf import PdfReader

from prism_api.reports.compare_report import build_compare_report_pdf
from prism_api.schemas.compare import CaseDiff, CompareResponse, MeasurementDiff, RunHeader


def _pdf_text(content: bytes) -> str:
    """Extract the rendered text from a generated PDF (asserts content, not just bytes)."""
    reader = PdfReader(io.BytesIO(content))
    return "\n".join(page.extract_text() for page in reader.pages)


_JUNIT = b"""<?xml version="1.0"?><testsuites>
<testsuite name="dsp" tests="2" failures="0" time="0.1">
<testcase classname="codec" name="ok" time="0.05">
<properties>
<property name="gain_dB" value="12.5"/>
<property name="gain_dB__unit" value="dB"/>
</properties>
</testcase>
<testcase classname="codec" name="other" time="0.05"/>
</testsuite></testsuites>"""


def _login(client: TestClient) -> str:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    return client.cookies.get("prism_csrf") or ""


def _upload(client: TestClient, csrf: str, name: str) -> str:
    resp = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", _JUNIT, "application/xml")},
        data={"metadata": json.dumps({"project_slug": "audio", "name": name})},
        headers={"X-Prism-Csrf": csrf},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_compare_report_pdf(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    a = _upload(client, csrf, "build-alpha")
    b = _upload(client, csrf, "build-beta")

    resp = client.get(f"/api/v1/compare/report.pdf?runs={a},{b}")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"
    assert "attachment" in resp.headers["content-disposition"]
    assert "comparison-report.pdf" in resp.headers["content-disposition"]

    # The report must actually render the comparison content, not be a blank page.
    text = _pdf_text(resp.content)
    assert "Comparison report" in text
    assert "Audio" in text  # project name
    assert "build-alpha" in text and "build-beta" in text  # both run names
    assert "Case status" in text
    assert "other" in text  # a case name from the uploaded suite
    assert "gain_dB" in text  # the measurement from the JUnit properties
    assert "12.5" in text  # its value


def test_compare_report_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/compare/report.pdf?runs=a,b").status_code == 401


def test_compare_report_empty_400(client: TestClient, seed_admin) -> None:
    _login(client)
    assert client.get("/api/v1/compare/report.pdf?runs=").status_code == 400


def test_compare_report_too_many_400(client: TestClient, seed_admin) -> None:
    _login(client)
    ids = ",".join(str(uuid.uuid4()) for _ in range(21))
    assert client.get(f"/api/v1/compare/report.pdf?runs={ids}").status_code == 400


def test_compare_report_unknown_404(client: TestClient, seed_admin) -> None:
    _login(client)
    ids = f"{uuid.uuid4()},{uuid.uuid4()}"
    assert client.get(f"/api/v1/compare/report.pdf?runs={ids}").status_code == 404


def test_build_compare_report_pdf_unit() -> None:
    from datetime import UTC, datetime

    data = CompareResponse(
        runs=[
            RunHeader(id="r1", name="run-1", status="pass", pass_count=2, fail_count=0),
            RunHeader(id="r2", name="run-2", status="mixed", pass_count=1, fail_count=1),
        ],
        cases=[
            CaseDiff(classname="c", name="ok", suite_name="dsp", statuses=["pass", "pass"]),
            CaseDiff(classname="c", name="other", suite_name="dsp", statuses=["pass", None]),
        ],
        pass_rate_delta=-0.5,
        measurement_diffs=[
            MeasurementDiff(name="gain_dB", unit="dB", values=[12.5, 11.0], delta=-1.5)
        ],
        boots=[None, None],
    )
    out = build_compare_report_pdf(
        data=data, project_names=["Audio"], generated_at=datetime(2026, 6, 1, tzinfo=UTC)
    )
    assert out[:5] == b"%PDF-"
    text = _pdf_text(out)
    assert "Comparison report" in text
    assert "run-1" in text and "run-2" in text
    assert "gain_dB" in text  # measurement row rendered
    assert "Case status" in text
    assert "other" in text  # case name rendered
