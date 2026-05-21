import io
import json
import zipfile


def _login(client):
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    return client.cookies.get("prism_csrf") or ""


def _boot(kernel):
    return f"Linux version 6.1.0-g{kernel} (j) #1\nHDL git hash: deadbeef1234\n".encode()


_JUNIT = (
    b'<?xml version="1.0"?><testsuites>'
    b'<testsuite name="s" tests="1" failures="0">'
    b'<testcase classname="c" name="t"/>'
    b"</testsuite></testsuites>"
)


def _upload(client, csrf, name, kernel):
    arc = io.BytesIO()
    with zipfile.ZipFile(arc, "w") as zf:
        zf.writestr("boot.log", _boot(kernel))
    return client.post(
        "/api/v1/runs",
        files={
            "junit": ("j.xml", _JUNIT, "application/xml"),
            "archive": ("a.zip", arc.getvalue(), "application/zip"),
        },
        data={"metadata": json.dumps({"project_slug": "rf", "name": name})},
        headers={"X-Prism-Csrf": csrf},
    ).json()["id"]


def test_commits_listing_and_filter(client, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "rf", "name": "RF"})
    _upload(client, csrf, "a", "1111111")
    _upload(client, csrf, "b", "1111111")
    _upload(client, csrf, "c", "2222222")

    commits = client.get("/api/v1/projects/rf/commits", params={"type": "kernel"}).json()
    by = {c["commit"]: c["run_count"] for c in commits}
    assert by == {"1111111": 2, "2222222": 1}

    runs = client.get("/api/v1/runs", params={"project": "rf", "kernel_commit": "1111111"}).json()
    assert sorted(r["name"] for r in runs) == ["a", "b"]
