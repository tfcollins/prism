import io
import json
import zipfile

import numpy as np
import pytest
from fastapi.testclient import TestClient


def _login(client: TestClient) -> str:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    return client.cookies.get("prism_csrf") or ""


def _bootstrap_with_waveform(client: TestClient, csrf: str) -> str:
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
        files={
            "junit": ("j.xml", junit, "application/xml"),
            "archive": ("a.zip", arc.getvalue(), "application/zip"),
        },
        data={"metadata": json.dumps({"project_slug": "audio", "name": "r1"})},
        headers={"X-Prism-Csrf": csrf},
    )
    run_id = resp.json()["id"]
    # Find the waveform artifact
    suites = client.get(f"/api/v1/runs/{run_id}").json()["suites"]
    cases = client.get(f"/api/v1/suites/{suites[0]['id']}/cases").json()
    case = client.get(f"/api/v1/cases/{cases[0]['id']}").json()
    waveform = next(a for a in case["artifacts"] if a["kind"] == "waveform_csv")
    return waveform["id"]


def test_artifact_metadata(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    art_id = _bootstrap_with_waveform(client, csrf)
    resp = client.get(f"/api/v1/artifacts/{art_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "waveform_csv"
    assert body["filename"].endswith("wave.csv")


def _bootstrap_with_spectrum(client: TestClient, csrf: str) -> str:
    client.post("/api/v1/projects", json={"slug": "rf", "name": "RF"})
    junit = b"""<?xml version="1.0"?><testsuites>
<testsuite name="rf" tests="1" failures="0" time="0.1">
<testcase classname="c" name="acpr" time="0.05"/>
</testsuite></testsuites>"""
    spec_csv = (
        "# center=2.4e9, span=20e6, rbw=10e3, unit=dBm\n2.39e9,-92.1\n2.40e9,-10.2\n2.41e9,-91.7\n"
    )
    arc = io.BytesIO()
    with zipfile.ZipFile(arc, "w") as zf:
        zf.writestr("rf__acpr__spectrum.csv", spec_csv)
    run_id = client.post(
        "/api/v1/runs",
        files={
            "junit": ("j.xml", junit, "application/xml"),
            "archive": ("a.zip", arc.getvalue(), "application/zip"),
        },
        data={"metadata": json.dumps({"project_slug": "rf", "name": "r1"})},
        headers={"X-Prism-Csrf": csrf},
    ).json()["id"]
    suites = client.get(f"/api/v1/runs/{run_id}").json()["suites"]
    cases = client.get(f"/api/v1/suites/{suites[0]['id']}/cases").json()
    case = client.get(f"/api/v1/cases/{cases[0]['id']}").json()
    spec = next(a for a in case["artifacts"] if a["kind"] == "spectrum_csv")
    return spec["id"]


def test_artifact_spectrum_endpoint(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    art_id = _bootstrap_with_spectrum(client, csrf)
    resp = client.get(f"/api/v1/artifacts/{art_id}/spectrum")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["unit"] == "dBm"
    assert body["frequencies"] == [2.39e9, 2.40e9, 2.41e9]
    assert body["powers"] == [-92.1, -10.2, -91.7]
    assert body["metadata"]["center"] == 2.4e9
    assert body["metadata"]["rbw"] == 10e3


def test_spectrum_endpoint_rejects_waveform(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    art_id = _bootstrap_with_waveform(client, csrf)
    resp = client.get(f"/api/v1/artifacts/{art_id}/spectrum")
    assert resp.status_code == 400


def _bootstrap_carrier_spectrum(client: TestClient, csrf: str) -> str:
    """A spectrum with a strong carrier at 1 GHz and weaker adjacent humps."""
    client.post("/api/v1/projects", json={"slug": "rf", "name": "RF"})
    junit = b"""<?xml version="1.0"?><testsuites>
<testsuite name="rf" tests="1" failures="0" time="0.1">
<testcase classname="c" name="acpr" time="0.05"/>
</testsuite></testsuites>"""
    lines = ["# center=1e9, span=400e6, unit=dBm"]
    for f in range(800_000_000, 1_200_000_001, 1_000_000):
        if 950e6 <= f <= 1050e6:
            p = -20.0
        elif 750e6 <= f <= 850e6 or 1150e6 <= f <= 1250e6:
            p = -55.0
        else:
            p = -120.0
        lines.append(f"{f},{p}")
    spec_csv = "\n".join(lines) + "\n"
    arc = io.BytesIO()
    with zipfile.ZipFile(arc, "w") as zf:
        zf.writestr("rf__acpr__spectrum.csv", spec_csv)
    run_id = client.post(
        "/api/v1/runs",
        files={
            "junit": ("j.xml", junit, "application/xml"),
            "archive": ("a.zip", arc.getvalue(), "application/zip"),
        },
        data={"metadata": json.dumps({"project_slug": "rf", "name": "r1"})},
        headers={"X-Prism-Csrf": csrf},
    ).json()["id"]
    suites = client.get(f"/api/v1/runs/{run_id}").json()["suites"]
    cases = client.get(f"/api/v1/suites/{suites[0]['id']}/cases").json()
    case = client.get(f"/api/v1/cases/{cases[0]['id']}").json()
    return next(a for a in case["artifacts"] if a["kind"] == "spectrum_csv")["id"]


def test_channel_power_and_acpr(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    art_id = _bootstrap_carrier_spectrum(client, csrf)
    resp = client.get(
        f"/api/v1/artifacts/{art_id}/channel-power",
        params={"center": 1e9, "channel_bw": 100e6, "offset": 200e6, "adjacent_bw": 100e6},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["channel_power_dbm"] is not None
    assert body["acpr_lower_dbc"] < -25
    assert body["acpr_upper_dbc"] < -25
    assert body["channel_band"] == [950e6, 1050e6]


def test_spurs_endpoint(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    art_id = _bootstrap_carrier_spectrum(client, csrf)
    resp = client.get(f"/api/v1/artifacts/{art_id}/spurs", params={"margin_db": 30})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["noise_floor_dbm"] < -50
    # The carrier region rises far above the floor → at least one spur reported.
    assert len(body["spurs"]) >= 1
    assert max(s["power"] for s in body["spurs"]) == pytest.approx(-20.0)


def test_artifact_waveform_endpoint(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    art_id = _bootstrap_with_waveform(client, csrf)
    resp = client.get(f"/api/v1/artifacts/{art_id}/waveform?downsample=400")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sample_rate"] == 8000
    assert body["total_samples"] == 2048
    assert 200 <= len(body["samples"]) <= 450  # downsampled


def test_artifact_fft_endpoint(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    art_id = _bootstrap_with_waveform(client, csrf)
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
    csrf = _login(client)
    art_id = _bootstrap_with_waveform(client, csrf)
    r1 = client.get(f"/api/v1/artifacts/{art_id}/fft?window=hann&nfft=1024&overlap=0.5")
    assert r1.status_code == 200
    r2 = client.get(f"/api/v1/artifacts/{art_id}/fft?window=hann&nfft=1024&overlap=0.5")
    assert r2.status_code == 200
    assert r1.json()["frequencies"] == r2.json()["frequencies"]


def _bootstrap_with_spectrogram(client: TestClient, csrf: str) -> str:
    client.post("/api/v1/projects", json={"slug": "rf2", "name": "RF2"})
    junit = b"""<?xml version="1.0"?><testsuites>
<testsuite name="rf" tests="1" failures="0" time="0.1">
<testcase classname="c" name="wf" time="0.05"/>
</testsuite></testsuites>"""
    sg_csv = (
        "# f_start=1e9, f_stop=2e9\n# t_start=0, t_step=0.5\n# unit=dBm\n-90,-85,-80\n-88,-70,-60\n"
    )
    arc = io.BytesIO()
    with zipfile.ZipFile(arc, "w") as zf:
        zf.writestr("rf__wf__waterfall.csv", sg_csv)
    run_id = client.post(
        "/api/v1/runs",
        files={
            "junit": ("j.xml", junit, "application/xml"),
            "archive": ("a.zip", arc.getvalue(), "application/zip"),
        },
        data={"metadata": json.dumps({"project_slug": "rf2", "name": "r1"})},
        headers={"X-Prism-Csrf": csrf},
    ).json()["id"]
    suites = client.get(f"/api/v1/runs/{run_id}").json()["suites"]
    cases = client.get(f"/api/v1/suites/{suites[0]['id']}/cases").json()
    case = client.get(f"/api/v1/cases/{cases[0]['id']}").json()
    return next(a for a in case["artifacts"] if a["kind"] == "spectrogram")["id"]


def test_spectrogram_endpoint(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    art_id = _bootstrap_with_spectrogram(client, csrf)
    body = client.get(f"/api/v1/artifacts/{art_id}/spectrogram").json()
    assert body["frequencies"] == [1e9, 1.5e9, 2e9]
    assert body["times"] == [0.0, 0.5]
    assert body["powers"] == [[-90, -85, -80], [-88, -70, -60]]
    assert body["unit"] == "dBm"
