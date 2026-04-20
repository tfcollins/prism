"""Run repository."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from prism_api.models.run import RunStatus, RunTag, TestRun


class RunRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, project_id: str, name: str, status: RunStatus, created_by: str | None = None) -> TestRun:
        run = TestRun(project_id=project_id, name=name, status=status, created_by=created_by)
        self._session.add(run)
        self._session.flush()
        return run

    def get_by_id(self, run_id: str) -> TestRun | None:
        return self._session.get(TestRun, run_id)

    def list_by_project(self, project_id: str) -> list[TestRun]:
        return list(
            self._session.execute(
                select(TestRun).where(TestRun.project_id == project_id).order_by(TestRun.created_at.desc())
            ).scalars()
        )

    def set_status(self, run_id: str, status: RunStatus) -> None:
        run = self._session.get(TestRun, run_id)
        if run is not None:
            run.status = status

    def set_junit_artifact(self, run_id: str, artifact_id: str) -> None:
        run = self._session.get(TestRun, run_id)
        if run is not None:
            run.junit_artifact_id = artifact_id

    def add_tag(self, run_id: str, key: str, value: str) -> RunTag:
        tag = RunTag(run_id=run_id, key=key, value=value)
        self._session.merge(tag)
        return tag

    def tags_for(self, run_id: str) -> list[RunTag]:
        return list(
            self._session.execute(select(RunTag).where(RunTag.run_id == run_id)).scalars()
        )
