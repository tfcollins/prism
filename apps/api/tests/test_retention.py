"""Retention prune: row deletes + content-addressed blob GC."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from prism_api.models.artifact import Artifact, ArtifactKind
from prism_api.models.project import Project
from prism_api.models.run import RunStatus, TestRun
from prism_api.models.suite import CaseStatus, TestCase, TestSuite
from prism_api.services.retention import prune_runs

CUTOFF = datetime(2026, 3, 1, tzinfo=UTC)


class FakeStorage:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete(self, key: str) -> None:
        self.deleted.append(key)


def _seed(db_session: Session) -> tuple[str, str]:
    project = Project(slug="p", name="P")
    db_session.add(project)
    db_session.flush()

    def make_run(name: str, created: datetime) -> tuple[str, str]:
        run = TestRun(project_id=project.id, name=name, status=RunStatus.PASS, created_at=created)
        db_session.add(run)
        db_session.flush()
        suite = TestSuite(run_id=run.id, name="s", pass_count=1, duration_ms=0)
        db_session.add(suite)
        db_session.flush()
        case = TestCase(suite_id=suite.id, classname="c", name="t", status=CaseStatus.PASS)
        db_session.add(case)
        db_session.flush()
        return run.id, case.id

    old_run, old_case = make_run("old", datetime(2026, 1, 1, tzinfo=UTC))
    new_run, _ = make_run("new", datetime(2026, 5, 1, tzinfo=UTC))

    def art(owner_type: str, owner_id: str, key: str) -> None:
        db_session.add(
            Artifact(
                owner_type=owner_type,
                owner_id=owner_id,
                kind=ArtifactKind.OTHER_BINARY,
                filename="f",
                size_bytes=1,
                content_hash="h",
                storage_key=key,
            )
        )

    art("run", old_run, "shared")  # same bytes as a new-run artifact
    art("case", old_case, "unique")  # only the old run references this
    art("run", new_run, "shared")  # keeps "shared" alive after the prune
    db_session.commit()
    return old_run, new_run


def test_prune_dry_run_changes_nothing(db_session: Session) -> None:
    old_run, _ = _seed(db_session)
    storage = FakeStorage()
    stats = prune_runs(db_session, storage, cutoff=CUTOFF, dry_run=True)  # type: ignore[arg-type]
    assert stats == {"runs": 1, "artifacts": 2, "blobs": 1, "dry_run": True}
    assert storage.deleted == []
    assert db_session.get(TestRun, old_run) is not None  # nothing deleted


def test_prune_deletes_old_run_and_orphan_blob_only(db_session: Session) -> None:
    old_run, new_run = _seed(db_session)
    storage = FakeStorage()
    stats = prune_runs(db_session, storage, cutoff=CUTOFF, dry_run=False)  # type: ignore[arg-type]

    assert stats["runs"] == 1
    assert stats["blobs"] == 1
    # The old run is gone; the recent one survives.
    assert db_session.get(TestRun, old_run) is None
    assert db_session.get(TestRun, new_run) is not None
    # "unique" was only referenced by the old run -> deleted; "shared" is still
    # referenced by the new run -> kept.
    assert storage.deleted == ["unique"]
