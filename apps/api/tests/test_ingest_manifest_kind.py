"""Verify ingest reads `kind` per attachment from manifest.json schema_version=2."""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from prism_api.ingest import IngestInputs, ingest_run
from prism_api.models import Artifact, Base
from prism_api.models.run import RunStatus
from prism_api.repos.projects import ProjectRepo
from prism_api.repos.runs import RunRepo
from prism_api.storage import ObjectStorage


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        yield s


@pytest.fixture
def storage() -> Iterator[ObjectStorage]:
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="prism")
        yield ObjectStorage(client=client, bucket="prism")


def _archive(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


_JUNIT = (
    b'<?xml version="1.0"?><testsuites>'
    b'<testsuite name="suite_x" tests="1" failures="0" errors="0" skipped="0">'
    b'<testcase classname="cls" name="case_a"/>'
    b'</testsuite></testsuites>'
)


def _setup_run(session: Session) -> str:
    project = ProjectRepo(session).create(slug="demo", name="Demo")
    session.flush()
    run = RunRepo(session).create(project_id=project.id, name="r1", status=RunStatus.PENDING)
    session.flush()
    return run.id


def test_legacy_archive_no_manifest_yields_null_manifest_kind(
    session: Session, storage: ObjectStorage,
) -> None:
    run_id = _setup_run(session)
    archive = _archive({
        "suite_x__case_a__spectrum.html": b"<html/>",
    })
    ingest_run(IngestInputs(run_id=run_id, junit_xml=_JUNIT, archive=archive),
               session=session, storage=storage)
    rows = session.query(Artifact).all()
    # All artifacts should have manifest_kind = None (no manifest.json in archive)
    assert all(r.manifest_kind is None for r in rows)


def test_v2_archive_with_manifest_kind_sets_manifest_kind(
    session: Session, storage: ObjectStorage,
) -> None:
    run_id = _setup_run(session)
    manifest = {
        "schema_version": 2, "run_meta": {}, "run_artifacts": [],
        "cases": [{
            "case_nodeid": "cls::case_a",
            "artifacts": [{
                "filename": "spectrum.html", "kind": "adi.iq",
                "rel_path": "cases/cls__case_a/adi.iq/spectrum.html",
                "size": 7,
            }],
        }],
    }
    archive = _archive({
        "manifest.json": json.dumps(manifest).encode("utf-8"),
        "suite_x__case_a__adi.iq__spectrum.html": b"<html/>",
    })
    ingest_run(IngestInputs(run_id=run_id, junit_xml=_JUNIT, archive=archive),
               session=session, storage=storage)
    fname = "suite_x__case_a__adi.iq__spectrum.html"
    rows = session.query(Artifact).filter_by(filename=fname).all()
    assert len(rows) == 1
    assert rows[0].manifest_kind == "adi.iq"
