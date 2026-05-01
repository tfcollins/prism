"""Repos for ingest-pipeline models."""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from prism_api.models import (
    ArtifactKind,
    Base,
    CaseStatus,
    DerivedKind,
    Project,
    RunStatus,
)
from prism_api.repos.artifacts import ArtifactRepo, DerivedRepo
from prism_api.repos.projects import ProjectRepo
from prism_api.repos.runs import RunRepo
from prism_api.repos.suites import CaseRepo, SuiteRepo


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        yield s


def _seed_project(session: Session) -> Project:
    p = ProjectRepo(session).create(slug="p", name="P")
    session.flush()
    return p


def test_run_and_tag_crud(session: Session) -> None:
    p = _seed_project(session)
    run_repo = RunRepo(session)
    run = run_repo.create(project_id=p.id, name="r1", status=RunStatus.PENDING)
    session.flush()

    run_repo.add_tag(run.id, "branch", "main")
    run_repo.add_tag(run.id, "sha", "abc")
    session.commit()

    assert run_repo.get_by_id(run.id) == run
    assert run_repo.list_by_project(p.id) == [run]
    assert {(t.key, t.value) for t in run_repo.tags_for(run.id)} == {
        ("branch", "main"),
        ("sha", "abc"),
    }

    run_repo.set_status(run.id, RunStatus.PASS)
    session.commit()
    assert run_repo.get_by_id(run.id).status == RunStatus.PASS


def test_suite_and_case_crud(session: Session) -> None:
    p = _seed_project(session)
    run = RunRepo(session).create(project_id=p.id, name="r", status=RunStatus.PENDING)
    session.flush()

    suite = SuiteRepo(session).create(run_id=run.id, name="dsp")
    session.flush()

    case = CaseRepo(session).create(
        suite_id=suite.id, classname="codec", name="sine", status=CaseStatus.PASS, duration_ms=5
    )
    session.commit()

    assert SuiteRepo(session).list_by_run(run.id) == [suite]
    assert CaseRepo(session).list_by_suite(suite.id) == [case]


def test_artifact_dedup_by_hash(session: Session) -> None:
    p = _seed_project(session)
    run = RunRepo(session).create(project_id=p.id, name="r", status=RunStatus.PENDING)
    session.flush()

    repo = ArtifactRepo(session)
    first = repo.create(
        owner_type="run",
        owner_id=run.id,
        kind=ArtifactKind.WAVEFORM_CSV,
        filename="a.csv",
        size_bytes=10,
        content_hash="h" * 64,
        storage_key="raw/hh/" + "h" * 64,
    )
    session.flush()

    # Same hash, different filename -> separate row but same storage_key
    second = repo.create(
        owner_type="run",
        owner_id=run.id,
        kind=ArtifactKind.WAVEFORM_CSV,
        filename="b.csv",
        size_bytes=10,
        content_hash="h" * 64,
        storage_key="raw/hh/" + "h" * 64,
    )
    session.commit()

    assert first.id != second.id
    assert first.storage_key == second.storage_key
    assert [a.filename for a in repo.list_by_owner("run", run.id)] == ["a.csv", "b.csv"]


def test_derived_artifact_lookup(session: Session) -> None:
    p = _seed_project(session)
    run = RunRepo(session).create(project_id=p.id, name="r", status=RunStatus.PENDING)
    session.flush()
    art = ArtifactRepo(session).create(
        owner_type="run",
        owner_id=run.id,
        kind=ArtifactKind.WAVEFORM_CSV,
        filename="a.csv",
        size_bytes=10,
        content_hash="h" * 64,
        storage_key="k",
    )
    session.flush()

    dr = DerivedRepo(session)
    d = dr.create(
        source_artifact_id=art.id,
        kind=DerivedKind.FFT,
        storage_key="derived/fft/x.npy",
        params_hash="p" * 32,
    )
    session.commit()

    assert dr.find(source_artifact_id=art.id, kind=DerivedKind.FFT, params_hash="p" * 32) == d
    assert dr.find(source_artifact_id=art.id, kind=DerivedKind.FFT, params_hash="other") is None
