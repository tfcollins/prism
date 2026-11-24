"""CLI fail-stale-pending: only old PENDING runs are flipped to ERROR."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from prism_api.cli import fail_stale_pending_cli
from prism_api.config import Settings
from prism_api.models import Base
from prism_api.models.project import Project
from prism_api.models.run import RunStatus, TestRun


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(  # type: ignore[call-arg]
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        s3_endpoint="http://x",
        s3_access_key="x",
        s3_secret_key="x",
        s3_bucket="x",
        redis_url="x",
        jwt_secret="testsecretlongenough",
    )


def _seed(settings: Settings) -> dict[str, str]:
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    rows = {
        "old_pending": (RunStatus.PENDING, now - timedelta(hours=3)),
        "new_pending": (RunStatus.PENDING, now - timedelta(minutes=5)),
        "old_pass": (RunStatus.PASS, now - timedelta(hours=3)),
    }
    ids: dict[str, str] = {}
    with sessionmaker(bind=engine)() as s:
        project = Project(slug="p", name="P")
        s.add(project)
        s.flush()
        for name, (status, created) in rows.items():
            run = TestRun(project_id=project.id, name=name, status=status, created_at=created)
            s.add(run)
            s.flush()
            ids[name] = run.id
        s.commit()
    engine.dispose()
    return ids


def _statuses(settings: Settings, ids: dict[str, str]) -> dict[str, RunStatus]:
    engine = create_engine(settings.database_url)
    with sessionmaker(bind=engine)() as s:
        out = {name: s.get(TestRun, rid).status for name, rid in ids.items()}  # type: ignore[union-attr]
    engine.dispose()
    return out


def test_marks_only_stale_pending(settings: Settings, capsys) -> None:
    ids = _seed(settings)
    fail_stale_pending_cli(settings, older_than_minutes=60)
    assert "marked 1 stale pending run(s)" in capsys.readouterr().out
    assert _statuses(settings, ids) == {
        "old_pending": RunStatus.ERROR,
        "new_pending": RunStatus.PENDING,
        "old_pass": RunStatus.PASS,
    }


def test_dry_run_changes_nothing(settings: Settings, capsys) -> None:
    ids = _seed(settings)
    fail_stale_pending_cli(settings, older_than_minutes=60, dry_run=True)
    out = capsys.readouterr().out
    assert ids["old_pending"] in out and "would mark 1" in out
    assert _statuses(settings, ids)["old_pending"] == RunStatus.PENDING
