"""Smoke tests for ingest-pipeline models against in-memory SQLite."""
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from prism_api.models import Base
from prism_api.models.artifact import Artifact, ArtifactKind, DerivedArtifact, DerivedKind
from prism_api.models.project import Project
from prism_api.models.run import RunStatus, RunTag, TestRun
from prism_api.models.suite import CaseStatus, TestCase, TestSuite


def test_full_run_tree_round_trip() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        project = Project(slug="a", name="A")
        s.add(project)
        s.flush()

        run = TestRun(
            project_id=project.id,
            name="nightly-42",
            status=RunStatus.PENDING,
            started_at=datetime.now(UTC),
        )
        s.add(run)
        s.flush()

        s.add_all([
            RunTag(run_id=run.id, key="branch", value="main"),
            RunTag(run_id=run.id, key="sha", value="abc123"),
        ])

        suite = TestSuite(run_id=run.id, name="dsp", pass_count=1, fail_count=0, error_count=0, skip_count=0, duration_ms=42)
        s.add(suite)
        s.flush()

        case = TestCase(suite_id=suite.id, classname="codec", name="sine_sweep", status=CaseStatus.PASS, duration_ms=10)
        s.add(case)
        s.flush()

        artifact = Artifact(
            owner_type="case",
            owner_id=case.id,
            kind=ArtifactKind.WAVEFORM_CSV,
            filename="sine.csv",
            size_bytes=1024,
            content_hash="deadbeef" * 8,
            storage_key="raw/de/deadbeef" + "deadbeef" * 7,
            metadata_json={"sample_rate": 48000},
        )
        s.add(artifact)
        s.flush()

        derived = DerivedArtifact(
            source_artifact_id=artifact.id,
            kind=DerivedKind.FFT,
            storage_key="derived/fft/x.npy",
            params_hash="f" * 32,
        )
        s.add(derived)
        s.commit()

        assert run.id and suite.id and case.id and artifact.id and derived.id
        tags = s.query(RunTag).filter(RunTag.run_id == run.id).all()
        assert {t.key for t in tags} == {"branch", "sha"}
