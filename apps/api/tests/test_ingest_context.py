# apps/api/tests/test_ingest_context.py
import io
import json
import zipfile


def _login(client) -> str:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    return client.cookies.get("prism_csrf") or ""


_CONTEXT = (
    b'<?xml version="1.0" encoding="utf-8"?>\n'
    b"<!DOCTYPE context [\n<!ELEMENT context (device | context-attribute)*>\n]>\n"
    b'<context name="local" description="Emulated Context">\n'
    b'  <device id="iio:device0" name="ad7291">\n'
    b'    <channel id="voltage0" type="input">\n'
    b'      <attribute name="raw" value="2048"/>\n'
    b"    </channel>\n"
    b"  </device>\n"
    b"</context>\n"
)


def test_ingest_detects_context_xml(client, seed_admin, patch_ingest) -> None:
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
        # Bare filename → run-scoped artifact.
        zf.writestr("context.xml", _CONTEXT)
    run_id = client.post(
        "/api/v1/runs",
        files={
            "junit": ("j.xml", junit, "application/xml"),
            "archive": ("a.zip", arc.getvalue(), "application/zip"),
        },
        data={"metadata": json.dumps({"project_slug": "rf", "name": "r1"})},
        headers={"X-Prism-Csrf": csrf},
    ).json()["id"]

    arts = client.get(f"/api/v1/runs/{run_id}/artifacts").json()
    ctx = [a for a in arts if a["kind"] == "iio_context_xml"]
    assert len(ctx) == 1
    assert ctx[0]["filename"].endswith("context.xml")
