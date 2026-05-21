# apps/api/tests/test_cli_reparse.py
from prism_api.cli import reparse_logs
from prism_api.models.artifact import Artifact, ArtifactKind
from prism_api.repos.logs import LogRepo


def test_reparse_builds_reports(db_session, monkeypatch) -> None:
    # an existing LOG_TEXT artifact with no report yet
    db_session.add(Artifact(
        id="a1", owner_type="run", owner_id="r1", kind=ArtifactKind.LOG_TEXT,
        filename="boot.log", size_bytes=10, content_hash="h", storage_key="k",
    ))
    db_session.flush()

    class FakeStorage:
        def get_bytes(self, key: str) -> bytes:
            return b"Linux version 6.1.0-gabc1234 (x) #1\n"

    n = reparse_logs(session=db_session, storage=FakeStorage(),
                     kernel_pattern="Linux version (\\S+)", hdl_pattern="x", findings_cap=50)
    assert n == 1
    reports = LogRepo(db_session).list_by_run("r1")
    assert reports[0].kernel_commit == "abc1234"
