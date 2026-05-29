"""End-to-end ingest flow using in-memory SQLite + moto S3 + synthetic archive."""

import io
import zipfile
from collections.abc import Iterator
from pathlib import Path

import boto3
import numpy as np
import pytest
from moto import mock_aws
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from prism_api.ingest import IngestInputs, ingest_run
from prism_api.models import Base
from prism_api.models.run import RunStatus
from prism_api.repos.artifacts import ArtifactRepo
from prism_api.repos.projects import ProjectRepo
from prism_api.repos.runs import RunRepo
from prism_api.repos.suites import CaseRepo, SuiteRepo
from prism_api.storage import ObjectStorage


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        yield s
    engine.dispose()


@pytest.fixture
def storage() -> Iterator[ObjectStorage]:
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="prism")
        yield ObjectStorage(client=client, bucket="prism")


def _make_archive() -> bytes:
    """Create an in-memory zip with a run-level log and a case-level CSV waveform."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.log", "run context goes here\n")
        samples = np.sin(np.linspace(0, 2 * np.pi, 512)).astype(np.float32)
        zf.writestr("dsp__sine_sweep_1khz__waveform.csv", "\n".join(str(x) for x in samples))
    return buf.getvalue()


def test_ingest_end_to_end(session: Session, storage: ObjectStorage) -> None:
    project = ProjectRepo(session).create(slug="audio", name="Audio")
    session.flush()

    junit_xml = (Path(__file__).parent / "fixtures" / "sample-junit.xml").read_bytes()
    archive = _make_archive()

    run = RunRepo(session).create(project_id=project.id, name="r1", status=RunStatus.PENDING)
    session.flush()

    ingest_run(
        IngestInputs(
            run_id=run.id,
            junit_xml=junit_xml,
            archive=archive,
        ),
        session=session,
        storage=storage,
    )
    session.commit()

    # Suites + cases created
    suites = SuiteRepo(session).list_by_run(run.id)
    assert {s.name for s in suites} == {"dsp", "api"}

    dsp = next(s for s in suites if s.name == "dsp")
    cases = CaseRepo(session).list_by_suite(dsp.id)
    assert {c.name for c in cases} == {"sine_sweep_1khz", "sine_sweep_5khz", "round_trip"}

    # Run-level log artifact exists
    run_artifacts = ArtifactRepo(session).list_by_owner("run", run.id)
    assert any(a.filename == "readme.log" for a in run_artifacts)
    assert any(a.kind.value == "junit_xml" for a in run_artifacts)

    # Case-level waveform CSV
    sine_1khz = next(c for c in cases if c.name == "sine_sweep_1khz")
    case_artifacts = ArtifactRepo(session).list_by_owner("case", sine_1khz.id)
    assert [a.filename for a in case_artifacts] == ["dsp__sine_sweep_1khz__waveform.csv"]
    assert case_artifacts[0].kind.value == "waveform_csv"

    # Run status flipped to `mixed` (sample JUnit has 1 failure out of 4)
    assert RunRepo(session).get_by_id(run.id).status == RunStatus.MIXED

    # junit_artifact_id set
    assert RunRepo(session).get_by_id(run.id).junit_artifact_id is not None


def test_ingest_all_pass_sets_pass_status(session: Session, storage: ObjectStorage) -> None:
    project = ProjectRepo(session).create(slug="audio", name="Audio")
    session.flush()

    all_pass_junit = b"""<?xml version="1.0"?>
<testsuites>
  <testsuite name="api" tests="1" failures="0" errors="0" skipped="0" time="0.05">
    <testcase classname="x" name="y" time="0.05"/>
  </testsuite>
</testsuites>"""

    run = RunRepo(session).create(project_id=project.id, name="r-ok", status=RunStatus.PENDING)
    session.flush()

    ingest_run(
        IngestInputs(run_id=run.id, junit_xml=all_pass_junit, archive=None),
        session=session,
        storage=storage,
    )
    session.commit()
    assert RunRepo(session).get_by_id(run.id).status == RunStatus.PASS


def test_ingest_without_junit_errors_the_run(session: Session, storage: ObjectStorage) -> None:
    project = ProjectRepo(session).create(slug="audio", name="Audio")
    session.flush()
    run = RunRepo(session).create(project_id=project.id, name="r-bad", status=RunStatus.PENDING)
    session.flush()

    ingest_run(
        IngestInputs(run_id=run.id, junit_xml=b"<not valid xml", archive=None),
        session=session,
        storage=storage,
    )
    session.commit()
    assert RunRepo(session).get_by_id(run.id).status == RunStatus.ERROR
