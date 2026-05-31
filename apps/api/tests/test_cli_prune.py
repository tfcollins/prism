"""CLI prune wrapper: disabled no-op + dry-run leaves data intact."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from prism_api.cli import prune_cli
from prism_api.config import Settings
from prism_api.models import Base
from prism_api.models.project import Project
from prism_api.models.run import RunStatus, TestRun


@pytest.fixture
def settings(tmp_path) -> Settings:
    db_path = tmp_path / "test.db"
    return Settings(  # type: ignore[call-arg]
        database_url=f"sqlite:///{db_path}",
        s3_endpoint="http://x",
        s3_access_key="x",
        s3_secret_key="x",
        s3_bucket="x",
        redis_url="x",
        jwt_secret="testsecretlongenough",
    )


def _seed_old_run(settings: Settings) -> str:
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        project = Project(slug="p", name="P")
        s.add(project)
        s.flush()
        run = TestRun(
            project_id=project.id,
            name="old",
            status=RunStatus.PASS,
            created_at=datetime.now(UTC) - timedelta(days=10),
        )
        s.add(run)
        s.commit()
        return run.id


def test_prune_disabled_is_noop(settings: Settings, capsys) -> None:
    run_id = _seed_old_run(settings)
    prune_cli(settings)  # retention_days defaults to 0 -> disabled
    assert "retention disabled" in capsys.readouterr().out
    engine = create_engine(settings.database_url)
    with sessionmaker(bind=engine)() as s:
        assert s.get(TestRun, run_id) is not None


def test_prune_dry_run_keeps_data(settings: Settings, capsys) -> None:
    run_id = _seed_old_run(settings)
    prune_cli(settings, days=1, dry_run=True)
    assert "would prune" in capsys.readouterr().out
    engine = create_engine(settings.database_url)
    with sessionmaker(bind=engine)() as s:
        assert s.get(TestRun, run_id) is not None  # dry-run deleted nothing
