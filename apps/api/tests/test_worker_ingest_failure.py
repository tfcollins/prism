"""Worker safety net: a failed ingest marks the run ERROR instead of stranding it PENDING."""

import io
import zipfile
from collections.abc import Iterator
from pathlib import Path

import boto3
import pytest
from moto import mock_aws
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from prism_api.ingest import IngestInputs, ingest_run
from prism_api.models import Base
from prism_api.models.run import RunStatus, TestRun
from prism_api.repos.logs import LogRepo
from prism_api.repos.projects import ProjectRepo
from prism_api.repos.runs import RunRepo
from prism_api.storage import ObjectStorage
from prism_api.worker import tasks

_JUNIT = (
    b'<?xml version="1.0"?><testsuites>'
    b'<testsuite name="s" tests="1" failures="0">'
    b'<testcase classname="c" name="t"/>'
    b"</testsuite></testsuites>"
)


@pytest.fixture
def factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(f"sqlite:///{tmp_path / 'w.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture
def storage() -> Iterator[ObjectStorage]:
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="prism")
        yield ObjectStorage(client=client, bucket="prism")


def _pending_run(factory: sessionmaker[Session]) -> str:
    with factory() as s:
        project = ProjectRepo(s).create(slug="p", name="P")
        s.flush()
        run = RunRepo(s).create(project_id=project.id, name="r", status=RunStatus.PENDING)
        s.commit()
        return run.id


def _ingest(factory: sessionmaker[Session], storage: ObjectStorage, run_id: str, key: str) -> None:
    tasks.ingest_or_mark_error(
        session_factory=factory,
        storage=storage,
        run_id=run_id,
        junit_xml_key=key,
        archive_key=None,
        kernel_pattern="",
        hdl_pattern="",
        findings_cap=200,
    )


def test_ingest_exception_marks_run_error(
    factory: sessionmaker[Session], storage: ObjectStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = _pending_run(factory)
    key = storage.put_raw(_JUNIT, filename="junit.xml")

    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("ingest exploded")

    monkeypatch.setattr(tasks, "ingest_run", boom)
    with pytest.raises(RuntimeError, match="exploded"):
        _ingest(factory, storage, run_id, key)
    with factory() as s:
        assert s.get(TestRun, run_id).status == RunStatus.ERROR  # type: ignore[union-attr]


def test_missing_blob_marks_run_error(
    factory: sessionmaker[Session], storage: ObjectStorage
) -> None:
    run_id = _pending_run(factory)
    with pytest.raises(Exception):  # noqa: B017 - any storage error must propagate
        _ingest(factory, storage, run_id, "raw/does-not-exist")
    with factory() as s:
        assert s.get(TestRun, run_id).status == RunStatus.ERROR  # type: ignore[union-attr]


def test_successful_ingest_sets_final_status(
    factory: sessionmaker[Session], storage: ObjectStorage
) -> None:
    run_id = _pending_run(factory)
    key = storage.put_raw(_JUNIT, filename="junit.xml")
    _ingest(factory, storage, run_id, key)
    with factory() as s:
        assert s.get(TestRun, run_id).status == RunStatus.PASS  # type: ignore[union-attr]


def test_failed_log_report_insert_does_not_poison_ingest(
    factory: sessionmaker[Session], storage: ObjectStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A DB error while saving a log report (e.g. NUL bytes on Postgres) must only drop
    that report; the run still reaches a final status."""
    run_id = _pending_run(factory)

    def failing_create_report(self: LogRepo, **kwargs: object) -> None:
        # Flush a row that violates NOT NULL, like Postgres rejecting NUL in text.
        self._session.add(TestRun(project_id=None, name=None))
        self._session.flush()

    monkeypatch.setattr(LogRepo, "create_report", failing_create_report)
    arc = io.BytesIO()
    with zipfile.ZipFile(arc, "w") as zf:
        zf.writestr("boot.log", b"[    1.0] <3> mmc0: error -84\n")
    with factory() as s:
        ingest_run(
            IngestInputs(run_id=run_id, junit_xml=_JUNIT, archive=arc.getvalue()),
            session=s,
            storage=storage,
        )
        s.commit()
    with factory() as s:
        assert s.get(TestRun, run_id).status == RunStatus.PASS  # type: ignore[union-attr]
