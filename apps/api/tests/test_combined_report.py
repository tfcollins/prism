"""Combined test-results PDF: endpoint (auth, validation, single+multi run) and
rendered content (flat Run-column tables, not a comparison)."""

import io
import json
import uuid

from fastapi.testclient import TestClient
from pypdf import PdfReader

from prism_api.reports.combined_report import (
    CombinedCaseRow,
    CombinedMeasurementRow,
    CombinedRunSummary,
    build_combined_report_pdf,
)


def _pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return "\n".join(page.extract_text() for page in reader.pages)


def _junit(gain: str) -> bytes:
    return f"""<?xml version="1.0"?><testsuites>
<testsuite name="rf" tests="2" failures="1" time="0.1">
<testcase classname="amp" name="gain_check" time="0.05">
<properties>
<property name="gain_dB" value="{gain}"/>
<property name="gain_dB__unit" value="dB"/>
<property name="gain_dB__max" value="20"/>
</properties>
</testcase>
<testcase classname="amp" name="noise_floor" time="0.05"><failure message="x">t</failure></testcase>
</testsuite></testsuites>""".encode()


def _login(client: TestClient) -> str:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    return client.cookies.get("prism_csrf") or ""


def _upload(client: TestClient, csrf: str, name: str, gain: str) -> str:
    resp = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", _junit(gain), "application/xml")},
        data={"metadata": json.dumps({"project_slug": "rf", "name": name})},
        headers={"X-Prism-Csrf": csrf},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_combined_report_single_run(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "rf", "name": "RF"})
    a = _upload(client, csrf, "solo-run", "12.5")

    resp = client.get(f"/api/v1/runs/report.pdf?runs={a}")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"
    assert "combined-report.pdf" in resp.headers["content-disposition"]

    text = _pdf_text(resp.content)
    assert "Combined test report" in text
    assert "solo-run" in text
    assert "gain_check" in text  # a test case
    assert "noise_floor" in text  # the failing case
    assert "gain_dB" in text and "12.5" in text  # measurement + value
    assert "PASS" in text  # in-spec (12.5 <= 20)


def test_combined_report_multi_run(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "rf", "name": "RF"})
    a = _upload(client, csrf, "run-a", "12.5")
    b = _upload(client, csrf, "run-b", "11.0")

    resp = client.get(f"/api/v1/runs/report.pdf?runs={a},{b}")
    assert resp.status_code == 200, resp.text
    text = _pdf_text(resp.content)
    # both runs appear as rows (flat combined table, not a comparison)
    assert "run-a" in text and "run-b" in text
    assert "11" in text  # run-b's gain value
    assert "Delta" not in text  # this is NOT the comparison report


def test_combined_report_empty_400(client: TestClient, seed_admin) -> None:
    _login(client)
    assert client.get("/api/v1/runs/report.pdf?runs=").status_code == 400


def test_combined_report_too_many_400(client: TestClient, seed_admin) -> None:
    _login(client)
    ids = ",".join(str(uuid.uuid4()) for _ in range(51))
    assert client.get(f"/api/v1/runs/report.pdf?runs={ids}").status_code == 400


def test_combined_report_unknown_404(client: TestClient, seed_admin) -> None:
    _login(client)
    assert client.get(f"/api/v1/runs/report.pdf?runs={uuid.uuid4()}").status_code == 404


def test_combined_report_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/runs/report.pdf?runs=a").status_code == 401


def test_build_combined_report_pdf_unit() -> None:
    from datetime import UTC, datetime

    out = build_combined_report_pdf(
        project_names=["RF"],
        summaries=[CombinedRunSummary("run-1", "mixed", 1, 1)],
        case_rows=[
            CombinedCaseRow("run-1", "rf", "gain_check", "pass"),
            CombinedCaseRow("run-1", "rf", "noise_floor", "fail"),
        ],
        measurement_rows=[
            CombinedMeasurementRow("run-1", "gain_dB", 12.5, "dB", None, 20.0, 7.5, True)
        ],
        generated_at=datetime(2026, 6, 2, tzinfo=UTC),
    )
    assert out[:5] == b"%PDF-"
    text = _pdf_text(out)
    assert "Combined test report" in text
    assert "run-1" in text
    assert "gain_check" in text and "noise_floor" in text
    assert "gain_dB" in text and "12.5" in text and "PASS" in text
