import json

from fastapi.testclient import TestClient


def _login(client: TestClient) -> str:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    return client.cookies.get("prism_csrf") or ""


def _upload(client: TestClient, csrf: str, name: str, tags: dict[str, str]) -> None:
    junit = b'<?xml version="1.0"?><testsuites><testsuite name="s" tests="1" failures="0"><testcase classname="c" name="t"/></testsuite></testsuites>'  # noqa: E501
    client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", junit, "application/xml")},
        data={"metadata": json.dumps({"project_slug": "rf", "name": name, "tags": tags})},
        headers={"X-Prism-Csrf": csrf},
    )


def test_tag_keys_values_and_filtered_runs(client: TestClient, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "rf", "name": "RF"})
    _upload(client, csrf, "r1", {"device_serial": "A1", "site": "lab"})
    _upload(client, csrf, "r2", {"device_serial": "A1"})
    _upload(client, csrf, "r3", {"device_serial": "B2"})

    keys = client.get("/api/v1/projects/rf/tag-keys").json()
    assert keys == ["device_serial", "site"]

    values = client.get("/api/v1/projects/rf/tag-values", params={"key": "device_serial"}).json()
    assert values == [
        {"value": "A1", "run_count": 2},
        {"value": "B2", "run_count": 1},
    ]

    # runs filtered to one DUT
    runs = client.get(
        "/api/v1/runs",
        params={"project": "rf", "tag_key": "device_serial", "tag_value": "A1"},
    ).json()
    assert sorted(r["name"] for r in runs) == ["r1", "r2"]
