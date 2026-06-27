import io
import json
import zipfile
from types import SimpleNamespace

import numpy as np

from prism_api.ingest import _genalyzer_enabled
from prism_api.repos.projects import ProjectRepo
from prism_api.repos.suites import MeasurementRepo, SuiteRepo


def _p(auto: bool) -> SimpleNamespace:
    return SimpleNamespace(genalyzer_auto=auto)


def test_genalyzer_enabled_truth_table() -> None:
    # project default (no tag)
    assert _genalyzer_enabled(_p(True), {}) is True
    assert _genalyzer_enabled(_p(False), {}) is False
    assert _genalyzer_enabled(None, {}) is False
    # a genalyzer tag overrides the project default
    assert _genalyzer_enabled(_p(False), {"genalyzer": "true"}) is True
    assert _genalyzer_enabled(_p(True), {"genalyzer": "false"}) is False
    # case-insensitive / variant values
    assert _genalyzer_enabled(_p(False), {"genalyzer": "YES"}) is True
    assert _genalyzer_enabled(_p(True), {"genalyzer": "off"}) is False
    # unrecognized tag value falls back to the project default
    assert _genalyzer_enabled(_p(True), {"genalyzer": "maybe"}) is True


def _login(client) -> str:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    return client.cookies.get("prism_csrf") or ""


def _upload_waveform(client, csrf, *, name, tags=None):
    junit = b"""<?xml version="1.0"?><testsuites>
<testsuite name="dsp" tests="1" failures="0" time="0.1">
<testcase classname="codec" name="tone" time="0.05"/>
</testsuite></testsuites>"""
    fs = 8000
    t = np.arange(2048) / fs
    sig = np.sin(2 * np.pi * 1000 * t) + 0.01 * np.sin(2 * np.pi * 3000 * t)
    csv = f"# sample_rate={fs}\n" + "\n".join(str(x) for x in sig) + "\n"
    arc = io.BytesIO()
    with zipfile.ZipFile(arc, "w") as zf:
        zf.writestr("dsp__tone__wave.csv", csv)
    meta = {"project_slug": "audio", "name": name, "tags": tags or {}}
    resp = client.post(
        "/api/v1/runs",
        files={
            "junit": ("j.xml", junit, "application/xml"),
            "archive": ("a.zip", arc.getvalue(), "application/zip"),
        },
        data={"metadata": json.dumps(meta)},
        headers={"X-Prism-Csrf": csrf},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _genalyzer_measurements(db_session, run_id):
    suite = SuiteRepo(db_session).list_by_run(run_id)[0]
    from prism_api.repos.suites import CaseRepo

    case = CaseRepo(db_session).list_by_suite(suite.id)[0]
    return {
        m.name: m
        for m in MeasurementRepo(db_session).list_by_case(case.id)
        if "genalyzer" in m.name
    }


def test_ingest_records_genalyzer_when_project_enabled(
    client, seed_admin, patch_ingest, db_session
) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    ProjectRepo(db_session).get_by_slug("audio").genalyzer_auto = True
    db_session.commit()

    run_id = _upload_waveform(client, csrf, name="r1")
    ms = _genalyzer_measurements(db_session, run_id)
    assert set(ms) == {
        "genalyzer.snr",
        "genalyzer.sfdr",
        "genalyzer.sinad",
        "genalyzer.thd",
        "genalyzer.enob",
    }
    assert ms["genalyzer.snr"].unit == "dB"
    assert ms["genalyzer.enob"].unit == "bits"
    assert ms["genalyzer.snr"].value > 30


def test_ingest_skips_genalyzer_when_disabled(client, seed_admin, patch_ingest, db_session) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    run_id = _upload_waveform(client, csrf, name="r1")
    assert _genalyzer_measurements(db_session, run_id) == {}


def test_ingest_run_tag_enables_genalyzer(client, seed_admin, patch_ingest, db_session) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    run_id = _upload_waveform(client, csrf, name="r1", tags={"genalyzer": "true"})
    assert "genalyzer.snr" in _genalyzer_measurements(db_session, run_id)
