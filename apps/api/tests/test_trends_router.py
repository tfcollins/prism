import json

from fastapi.testclient import TestClient


def _login(client: TestClient) -> str:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    return client.cookies.get("prism_csrf") or ""


def _junit_with_cp(value: float) -> bytes:
    return f"""<?xml version="1.0"?><testsuites>
<testsuite name="rf" tests="1" failures="0" time="0.1">
<testcase classname="acpr" name="lower" time="0.05">
<properties>
<property name="channel_power_dBm" value="{value}"/>
<property name="channel_power_dBm__unit" value="dBm"/>
<property name="channel_power_dBm__max" value="-9.0"/>
</properties>
</testcase>
</testsuite></testsuites>""".encode()


def _upload(client: TestClient, csrf: str, name: str, value: float) -> None:
    client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", _junit_with_cp(value), "application/xml")},
        data={"metadata": json.dumps({"project_slug": "rf", "name": name, "tags": {"sha": name}})},
        headers={"X-Prism-Csrf": csrf},
    )


def test_measurement_names_and_trend(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "rf", "name": "RF"})
    _upload(client, csrf, "build-1", -10.5)
    _upload(client, csrf, "build-2", -8.0)  # over the -9.0 ceiling → fail

    names = client.get("/api/v1/projects/rf/measurements").json()
    assert names == ["channel_power_dBm"]

    trend = client.get("/api/v1/projects/rf/measurements/channel_power_dBm/trend").json()
    assert trend["measurement_name"] == "channel_power_dBm"
    assert [p["run_name"] for p in trend["points"]] == ["build-1", "build-2"]
    assert [p["value"] for p in trend["points"]] == [-10.5, -8.0]
    assert [p["in_spec"] for p in trend["points"]] == [True, False]
    assert trend["points"][0]["tags"] == {"sha": "build-1"}


def test_trend_unknown_project_404(client: TestClient, seed_admin) -> None:
    _login(client)
    assert client.get("/api/v1/projects/nope/measurements").status_code == 404
    assert client.get("/api/v1/projects/nope/measurements/x/trend").status_code == 404


def test_regressions(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "rf", "name": "RF"})
    # spec_max is -9.0 in _junit_with_cp; -10.5 passes, -8.0 fails, -7.0 fails
    _upload(client, csrf, "build-1", -10.5)  # in spec
    _upload(client, csrf, "build-2", -8.0)  # crosses out
    _upload(client, csrf, "build-3", -7.0)  # still out

    events = client.get("/api/v1/projects/rf/regressions").json()["events"]
    by_run = {e["run_name"]: e for e in events}
    assert "build-1" not in by_run  # in spec, no event
    assert by_run["build-2"]["kind"] == "crossed_out"
    assert by_run["build-2"]["previous_value"] == -10.5
    assert by_run["build-3"]["kind"] == "still_out"
    # newest first
    assert events[0]["run_name"] == "build-3"
