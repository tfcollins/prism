"""Provenance and captured output through the real upload/ingest/read paths."""

import io
import json
import zipfile

from prism_api.models.run import TestRun


def upload(client, *, metadata=None, archive=None, junit=None):
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    client.post("/api/v1/projects", json={"slug": "provenance", "name": "Provenance"})
    default_junit = (
        b'<testsuites><testsuite name="pytest">'
        b'<testcase classname="test_a" name="test_pass">'
        b"<system-out>passing stdout\n</system-out>"
        b"<system-err>passing stderr\n</system-err>"
        b"</testcase></testsuite></testsuites>"
    )
    files = {"junit": ("junit.xml", junit or default_junit, "application/xml")}
    if archive:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for name, data in archive.items():
                zf.writestr(name, data)
        files["archive"] = ("archive.zip", buf.getvalue(), "application/zip")
    response = client.post(
        "/api/v1/runs",
        files=files,
        data={
            "metadata": json.dumps(
                {"project_slug": "provenance", "name": "result", **(metadata or {})}
            )
        },
        headers={"X-Prism-Csrf": client.cookies.get("prism_csrf") or ""},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_metadata_roundtrip(client, seed_admin, patch_ingest, db_session):
    ci = {
        "provider": "github",
        "repository": "org/repo",
        "run_id": "123",
        "attempt": "2",
        "job_name": "hw",
        "matrix": {"board": "adc"},
        "run_url": "https://github.com/org/repo/actions/runs/123/attempts/2",
    }
    hardware = {
        "place": "reserved-place",
        "board": "adc",
        "carrier": "carrier",
        "exporters": ["exporter"],
        "tags": {"hdl-config": "rx"},
        "collection_errors": ["dmesg post failed"],
    }
    result = upload(
        client, metadata={"ci": ci, "hardware": hardware, "started_at": "2026-11-10T12:00:00Z"}
    )
    run = db_session.get(TestRun, result["id"])
    assert run.ci == ci
    assert run.hardware == hardware
    assert result["ci"] == ci
    detail = client.get(f"/api/v1/runs/{result['id']}").json()
    assert detail["ci"] == ci
    assert detail["hardware"] == hardware
    assert detail["started_at"].startswith("2026-11-10T12:00:00")


def test_passing_junit_captured_output_is_case_artifacts(client, seed_admin, patch_ingest):
    run = upload(client)
    detail = client.get(f"/api/v1/runs/{run['id']}").json()
    cases = client.get(f"/api/v1/suites/{detail['suites'][0]['id']}/cases").json()
    case = client.get(f"/api/v1/cases/{cases[0]['id']}").json()
    captured = {a["filename"]: a for a in case["artifacts"]}
    assert {"system-out.log", "system-err.log"} <= captured.keys()
    raw = client.get(f"/api/v1/artifacts/{captured['system-out.log']['id']}/raw")
    assert raw.content == b"passing stdout\n"
    assert detail["ci"] is None
    assert detail["hardware"] is None


def test_recovers_legacy_session_context_and_tag_ci(client, seed_admin, patch_ingest, db_session):
    pre = {
        "place": "actual-place",
        "tags": {"daughter-board": "adc", "carrier": "zcu"},
        "exporters": ["exporter"],
    }
    post = {"dmesg_post_error": "SSH failed"}
    run = upload(
        client,
        metadata={"tags": {"ci_url": "https://github.com/org/repo/actions/runs/7"}},
        archive={
            "run_meta.json": json.dumps(
                {"session_pre": {"labgrid": pre}, "session_post": {"labgrid": post}}
            )
        },
    )
    assert client.get(f"/api/v1/runs/{run['id']}/logs").json() == []
    # Simulate historical rows whose new columns have never been populated.
    row = db_session.get(TestRun, run["id"])
    row.ci = None
    row.hardware = None
    db_session.commit()
    detail = client.get(f"/api/v1/runs/{run['id']}").json()
    assert detail["ci"]["run_url"] == "https://github.com/org/repo/actions/runs/7"
    assert detail["hardware"]["place"] == "actual-place"
    assert detail["hardware"]["board"] == "adc"
    assert "SSH failed" in detail["hardware"]["collection_errors"]


def test_manifest_ownership_distinguishes_same_named_tests(client, seed_admin, patch_ingest):
    junit = (
        b"<testsuites>"
        b'<testsuite name="pytest">'
        b'<testcase classname="test_a" name="test_same"/>'
        b'<testcase classname="test_b" name="test_same"/>'
        b"</testsuite>"
        b"</testsuites>"
    )
    mapping = [
        {
            "filename": "cases/a/pytest_stdout_call.log",
            "suite": "pytest",
            "classname": "test_a",
            "case": "test_same",
            "kind": "pytest_capture",
        },
        {
            "filename": "cases/b/pytest_stdout_call.log",
            "suite": "pytest",
            "classname": "test_b",
            "case": "test_same",
            "kind": "pytest_capture",
        },
    ]
    run = upload(
        client,
        junit=junit,
        archive={
            "manifest.json": json.dumps({"schema_version": 2, "archive_artifacts": mapping}),
            "cases/a/pytest_stdout_call.log": "first test\n",
            "cases/b/pytest_stdout_call.log": "second test\n",
        },
    )
    detail = client.get(f"/api/v1/runs/{run['id']}").json()
    cases = client.get(f"/api/v1/suites/{detail['suites'][0]['id']}/cases").json()
    for case, expected in zip(cases, [b"first test\n", b"second test\n"], strict=True):
        artifacts = client.get(f"/api/v1/cases/{case['id']}").json()["artifacts"]
        assert len(artifacts) == 1
        assert client.get(f"/api/v1/artifacts/{artifacts[0]['id']}/raw").content == expected


def test_malformed_legacy_metadata_keeps_run_readable(client, seed_admin, patch_ingest):
    run = upload(client, archive={"run_meta.json": json.dumps({"ci": "bad", "session_pre": None})})
    response = client.get(f"/api/v1/runs/{run['id']}")
    assert response.status_code == 200
    assert response.json()["ci"] is None
    assert response.json()["hardware"] is None


def test_migration_preserves_historical_rows():
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, text

    source = Path(__file__).parents[1] / "src/prism_api/migrations/versions/0017_run_provenance.py"
    spec = importlib.util.spec_from_file_location("run_provenance_migration", source)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE test_runs (id TEXT PRIMARY KEY, name TEXT)"))
        connection.execute(text("INSERT INTO test_runs VALUES ('old', 'historical')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            row = connection.execute(text("SELECT name, ci, hardware FROM test_runs")).one()
            assert row == ("historical", None, None)
            migration.downgrade()
            assert connection.execute(text("SELECT name FROM test_runs")).scalar() == "historical"
    engine.dispose()


def test_incomplete_junit_preserves_archive_and_marks_error(client, seed_admin, patch_ingest):
    run = upload(
        client,
        junit=(
            b'<testsuites><testsuite name="pytest"><testcase time="0.0"/></testsuite></testsuites>'
        ),
        archive={"terminal.log": "KeyboardInterrupt\n"},
    )
    assert run["status"] == "error"
    artifacts = client.get(f"/api/v1/runs/{run['id']}/artifacts").json()
    terminal = next(a for a in artifacts if a["filename"] == "terminal.log")
    assert client.get(f"/api/v1/artifacts/{terminal['id']}/raw").content == b"KeyboardInterrupt\n"
