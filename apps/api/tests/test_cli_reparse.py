# apps/api/tests/test_cli_reparse.py
from prism_api.cli import reparse_logs
from prism_api.models.artifact import Artifact, ArtifactKind
from prism_api.models.suite import TestCase, TestSuite
from prism_api.repos.logs import LogRepo


class _FakeStorage:
    def get_bytes(self, key: str) -> bytes:
        return b"Linux version 6.1.0-gabc1234 (x) #1\n"


def test_reparse_builds_reports(db_session, monkeypatch) -> None:
    # an existing LOG_TEXT artifact with no report yet
    db_session.add(
        Artifact(
            id="a1",
            owner_type="run",
            owner_id="r1",
            kind=ArtifactKind.LOG_TEXT,
            filename="boot.log",
            size_bytes=10,
            content_hash="h",
            storage_key="k",
        )
    )
    db_session.flush()

    n = reparse_logs(
        session=db_session,
        storage=_FakeStorage(),
        kernel_pattern="Linux version (\\S+)",
        hdl_pattern="x",
        findings_cap=50,
    )
    assert n == 1
    reports = LogRepo(db_session).list_by_run("r1")
    assert reports[0].kernel_commit == "abc1234"


def test_reparse_case_scoped_artifact_resolves_to_run(db_session) -> None:
    """A case-scoped LOG_TEXT artifact must produce a LogReport stored under the run id."""
    # Build the suite/case hierarchy so _resolve_run_id can follow FKs via session.get()
    suite = TestSuite(id="suite1", run_id="run1", name="MySuite")
    case = TestCase(id="case1", suite_id="suite1", name="MyCase", status="pass")
    db_session.add(suite)
    db_session.add(case)
    artifact = Artifact(
        id="a2",
        owner_type="case",
        owner_id="case1",
        kind=ArtifactKind.LOG_TEXT,
        filename="dmesg.log",
        size_bytes=20,
        content_hash="h2",
        storage_key="k2",
    )
    db_session.add(artifact)
    db_session.flush()

    n = reparse_logs(
        session=db_session,
        storage=_FakeStorage(),
        kernel_pattern=r"Linux version (\S+)",
        hdl_pattern="x",
        findings_cap=50,
    )
    assert n == 1
    # The report must be stored under the run id, not the case id
    reports = LogRepo(db_session).list_by_run("run1")
    assert len(reports) == 1
    assert reports[0].run_id == "run1"
    # Ensure nothing was stored under the case id
    assert LogRepo(db_session).list_by_run("case1") == []
