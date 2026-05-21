import io
import json
import zipfile


def _login(client):
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    return client.cookies.get("prism_csrf") or ""


_BOOT = b"Linux version 6.1.0-g1a2b3c4 (j) #1\nHDL git hash: deadbeef1234\n<3> mmc0: error\n"

_JUNIT = (
    b'<?xml version="1.0"?><testsuites><testsuite name="s" tests="1" failures="0">'
    b'<testcase classname="c" name="t"/></testsuite></testsuites>'
)


def _upload(client, csrf, name):
    junit = _JUNIT
    arc = io.BytesIO()
    with zipfile.ZipFile(arc, "w") as zf:
        zf.writestr("boot.log", _BOOT)
    return client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", junit, "application/xml"),
               "archive": ("a.zip", arc.getvalue(), "application/zip")},
        data={"metadata": json.dumps({"project_slug": "rf", "name": name})},
        headers={"X-Prism-Csrf": csrf},
    ).json()["id"]


def test_run_logs_and_boot_summary(client, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "rf", "name": "RF"})
    run_id = _upload(client, csrf, "r1")

    logs = client.get(f"/api/v1/runs/{run_id}/logs").json()
    assert logs[0]["kernel_commit"] == "1a2b3c4"
    assert logs[0]["hdl_commit"] == "deadbeef1234"
    assert any(f["severity"] == "error" for f in logs[0]["findings"])

    detail = client.get(f"/api/v1/runs/{run_id}").json()
    assert detail["boot"]["kernel_commit"] == "1a2b3c4"
    assert detail["boot"]["error_count"] == 1
