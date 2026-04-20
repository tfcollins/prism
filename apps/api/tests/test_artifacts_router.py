import io
import json
import zipfile

import numpy as np
from fastapi.testclient import TestClient


def _login(client: TestClient) -> None:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})


def _bootstrap_with_waveform(client: TestClient) -> str:
    client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    junit = b"""<?xml version="1.0"?><testsuites>
<testsuite name="dsp" tests="1" failures="0" time="0.1">
<testcase classname="c" name="ok" time="0.05"/>
</testsuite></testsuites>"""
    # 1kHz sine at fs=8kHz, 2048 samples
    fs = 8000
    t = np.arange(2048) / fs
    samples = np.sin(2 * np.pi * 1000 * t)
    csv = f"# sample_rate={fs}\n" + "\n".join(str(x) for x in samples) + "\n"
    arc = io.BytesIO()
    with zipfile.ZipFile(arc, "w") as zf:
        zf.writestr("dsp__ok__wave.csv", csv)
    resp = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", junit, "application/xml"), "archive": ("a.zip", arc.getvalue(), "application/zip")},
        data={"metadata": json.dumps({"project_slug": "audio", "name": "r1"})},
    )
    run_id = resp.json()["id"]
    # Find the waveform artifact
    suites = client.get(f"/api/v1/runs/{run_id}").json()["suites"]
    cases = client.get(f"/api/v1/suites/{suites[0]['id']}/cases").json()
    case = client.get(f"/api/v1/cases/{cases[0]['id']}").json()
    waveform = next(a for a in case["artifacts"] if a["kind"] == "waveform_csv")
    return waveform["id"]


def test_artifact_metadata(client: TestClient, seed_admin, patch_ingest) -> None:
    _login(client)
    art_id = _bootstrap_with_waveform(client)
    resp = client.get(f"/api/v1/artifacts/{art_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "waveform_csv"
    assert body["filename"].endswith("wave.csv")


def test_artifact_waveform_endpoint(client: TestClient, seed_admin, patch_ingest) -> None:
    _login(client)
    art_id = _bootstrap_with_waveform(client)
    resp = client.get(f"/api/v1/artifacts/{art_id}/waveform?downsample=400")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sample_rate"] == 8000
    assert body["total_samples"] == 2048
    assert 200 <= len(body["samples"]) <= 450  # downsampled


def test_artifact_fft_endpoint(client: TestClient, seed_admin, patch_ingest) -> None:
    _login(client)
    art_id = _bootstrap_with_waveform(client)
    resp = client.get(f"/api/v1/artifacts/{art_id}/fft?window=hann&nfft=1024&overlap=0.5")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["frequencies"]) == len(body["magnitudes"])
    # peak should land near 1000 Hz
    freqs = body["frequencies"]
    mags = body["magnitudes"]
    peak_idx = max(range(len(mags)), key=lambda i: mags[i])
    assert abs(freqs[peak_idx] - 1000) < 50


def test_artifact_fft_cached_second_call(client: TestClient, seed_admin, patch_ingest) -> None:
    _login(client)
    art_id = _bootstrap_with_waveform(client)
    r1 = client.get(f"/api/v1/artifacts/{art_id}/fft?window=hann&nfft=1024&overlap=0.5")
    assert r1.status_code == 200
    r2 = client.get(f"/api/v1/artifacts/{art_id}/fft?window=hann&nfft=1024&overlap=0.5")
    assert r2.status_code == 200
    assert r1.json()["frequencies"] == r2.json()["frequencies"]
