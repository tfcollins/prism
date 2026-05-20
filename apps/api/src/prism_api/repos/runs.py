"""Run repository."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from prism_api.models.run import RunStatus, RunTag, TestRun
from prism_api.models.suite import TestSuite


class RunRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self, *, project_id: str, name: str, status: RunStatus, created_by: str | None = None
    ) -> TestRun:
        run = TestRun(project_id=project_id, name=name, status=status, created_by=created_by)
        self._session.add(run)
        self._session.flush()
        return run

    def get_by_id(self, run_id: str) -> TestRun | None:
        return self._session.get(TestRun, run_id)

    def list_by_project(self, project_id: str) -> list[TestRun]:
        return list(
            self._session.execute(
                select(TestRun)
                .where(TestRun.project_id == project_id)
                .order_by(TestRun.created_at.desc())
            ).scalars()
        )

    def set_status(self, run_id: str, status: RunStatus) -> None:
        run = self._session.get(TestRun, run_id)
        if run is not None:
            run.status = status

    def set_calibration_run(self, run_id: str, calibration_run_id: str | None) -> None:
        run = self._session.get(TestRun, run_id)
        if run is not None:
            run.calibration_run_id = calibration_run_id

    def set_junit_artifact(self, run_id: str, artifact_id: str) -> None:
        run = self._session.get(TestRun, run_id)
        if run is not None:
            run.junit_artifact_id = artifact_id

    def add_tag(self, run_id: str, key: str, value: str) -> RunTag:
        tag = RunTag(run_id=run_id, key=key, value=value)
        self._session.merge(tag)
        return tag

    def tags_for(self, run_id: str) -> list[RunTag]:
        return list(self._session.execute(select(RunTag).where(RunTag.run_id == run_id)).scalars())

    def list_with_filters(
        self,
        *,
        project_id: str,
        status: str | None = None,
        tag_key: str | None = None,
        tag_value: str | None = None,
        limit: int = 50,
    ) -> list[TestRun]:
        stmt = select(TestRun).where(TestRun.project_id == project_id)
        if status:
            stmt = stmt.where(TestRun.status == RunStatus(status))
        if tag_key is not None and tag_value is not None:
            stmt = stmt.join(RunTag, RunTag.run_id == TestRun.id).where(
                RunTag.key == tag_key, RunTag.value == tag_value
            )
        stmt = stmt.order_by(TestRun.created_at.desc()).limit(limit)
        return list(self._session.execute(stmt).scalars())

    def distinct_tag_keys(self, project_id: str) -> list[str]:
        rows = self._session.execute(
            select(RunTag.key)
            .join(TestRun, TestRun.id == RunTag.run_id)
            .where(TestRun.project_id == project_id)
            .distinct()
            .order_by(RunTag.key)
        ).scalars()
        return list(rows)

    def tag_value_counts(self, project_id: str, key: str) -> list[tuple[str, int]]:
        rows = self._session.execute(
            select(RunTag.value, func.count())
            .join(TestRun, TestRun.id == RunTag.run_id)
            .where(TestRun.project_id == project_id, RunTag.key == key)
            .group_by(RunTag.value)
            .order_by(RunTag.value)
        ).all()
        return [(str(v), int(c)) for v, c in rows]

    def aggregate_counts_by_run(self, run_id: str) -> dict[str, int]:
        row = self._session.execute(
            select(
                func.coalesce(func.sum(TestSuite.pass_count), 0),
                func.coalesce(func.sum(TestSuite.fail_count), 0),
                func.coalesce(func.sum(TestSuite.error_count), 0),
                func.coalesce(func.sum(TestSuite.skip_count), 0),
            ).where(TestSuite.run_id == run_id)
        ).one()
        return {
            "pass_count": int(row[0]),
            "fail_count": int(row[1]),
            "error_count": int(row[2]),
            "skip_count": int(row[3]),
        }
