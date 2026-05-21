# apps/api/tests/test_ingest_logs.py
import io
import json
import zipfile

from prism_api.repos.logs import LogRepo


def _login(client) -> str:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    return client.cookies.get("prism_csrf") or ""


_BOOT = b"""[    0.000000] Linux version 6.1.0-g1a2b3c4 (j@b) #1 SMP
[    0.000000] Machine model: Analog Devices ZCU102
HDL git hash: deadbeef1234
[    1.0] <3> mmc0: error -84
[    2.0] Kernel panic - not syncing
"""


def test_ingest_parses_boot_log(client, seed_admin, patch_ingest, db_session) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "rf", "name": "RF"})
    junit = (
        b'<?xml version="1.0"?><testsuites>'
        b'<testsuite name="s" tests="1" failures="0">'
        b'<testcase classname="c" name="t"/>'
        b"</testsuite></testsuites>"
    )
    arc = io.BytesIO()
    with zipfile.ZipFile(arc, "w") as zf:
        zf.writestr("boot.log", _BOOT)
    run_id = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", junit, "application/xml"),
               "archive": ("a.zip", arc.getvalue(), "application/zip")},
        data={"metadata": json.dumps({"project_slug": "rf", "name": "r1"})},
        headers={"X-Prism-Csrf": csrf},
    ).json()["id"]

    reports = LogRepo(db_session).list_by_run(run_id)
    assert len(reports) == 1
    assert reports[0].kernel_commit == "1a2b3c4"
    assert reports[0].hdl_commit == "deadbeef1234"
    assert reports[0].has_panic is True
    assert reports[0].error_count == 1
