"""Database-wide aggregate queries for the landing/overview page."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from prism_api.models.project import Project
from prism_api.models.run import TestRun
from prism_api.models.suite import TestSuite


class StatsRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def totals(self) -> dict[str, int]:
        """Counts of projects/runs and summed test-case outcomes across everything."""
        projects = self._session.scalar(select(func.count()).select_from(Project)) or 0
        runs = self._session.scalar(select(func.count()).select_from(TestRun)) or 0
        passed, failed, errored, skipped = self._session.execute(
            select(
                func.coalesce(func.sum(TestSuite.pass_count), 0),
                func.coalesce(func.sum(TestSuite.fail_count), 0),
                func.coalesce(func.sum(TestSuite.error_count), 0),
                func.coalesce(func.sum(TestSuite.skip_count), 0),
            )
        ).one()
        return {
            "total_projects": int(projects),
            "total_runs": int(runs),
            "passed": int(passed),
            "failed": int(failed),
            "errored": int(errored),
            "skipped": int(skipped),
        }

    def recent_runs(self, limit: int = 10) -> list[tuple[TestRun, str, str]]:
        """Most recent runs across all projects, with the owning project's slug + name."""
        rows = self._session.execute(
            select(TestRun, Project.slug, Project.name)
            .join(Project, Project.id == TestRun.project_id)
            .order_by(TestRun.created_at.desc())
            .limit(limit)
        ).all()
        return [(row[0], row[1], row[2]) for row in rows]

    def daily_run_failures(self, days: int = 30) -> list[tuple[datetime, int]]:
        """Per-run (created_at, failed+errored cases) within the window.

        Bucketing into days happens in Python so this stays portable across
        SQLite (tests) and Postgres (no DB-specific date functions).
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)
        rows = self._session.execute(
            select(
                TestRun.created_at,
                func.coalesce(func.sum(TestSuite.fail_count), 0)
                + func.coalesce(func.sum(TestSuite.error_count), 0),
            )
            .outerjoin(TestSuite, TestSuite.run_id == TestRun.id)
            .where(TestRun.created_at >= cutoff)
            .group_by(TestRun.id, TestRun.created_at)
        ).all()
        return [(row[0], int(row[1])) for row in rows]
