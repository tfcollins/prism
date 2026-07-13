"""Run repository."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from prism_api.models.artifact import Artifact, ArtifactKind
from prism_api.models.log import LogReport
from prism_api.models.run import RunStatus, RunTag, TestRun
from prism_api.models.suite import TestCase, TestSuite

# Artifact kinds that render as a plottable figure in the UI (waveforms, spectra,
# spectrograms, images). Excludes wav_audio (audio playback, not a plot) and
# Plotly figure JSON, which currently arrives as log_text from kind detection.
FIGURE_KINDS: frozenset[ArtifactKind] = frozenset(
    {
        ArtifactKind.WAVEFORM_CSV,
        ArtifactKind.WAVEFORM_HDF5,
        ArtifactKind.WAVEFORM_NPY,
        ArtifactKind.SPECTRUM_CSV,
        ArtifactKind.SPECTRUM_TOUCHSTONE,
        ArtifactKind.SPECTROGRAM,
        ArtifactKind.IMAGE_PNG,
    }
)


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

    def get_tag(self, run_id: str, key: str) -> RunTag | None:
        return self._session.get(RunTag, (run_id, key))

    def create_tag(self, run_id: str, key: str, value: str) -> RunTag:
        tag = RunTag(run_id=run_id, key=key, value=value)
        self._session.add(tag)
        self._session.flush()
        return tag

    def update_tag(self, run_id: str, key: str, value: str) -> RunTag | None:
        tag = self.get_tag(run_id, key)
        if tag is None:
            return None
        tag.value = value
        return tag

    def delete_tag(self, run_id: str, key: str) -> bool:
        tag = self.get_tag(run_id, key)
        if tag is None:
            return False
        self._session.delete(tag)
        self._session.flush()
        return True

    def tags_for(self, run_id: str) -> list[RunTag]:
        return list(self._session.execute(select(RunTag).where(RunTag.run_id == run_id)).scalars())

    def list_with_filters(
        self,
        *,
        project_id: str,
        status: str | None = None,
        tag_key: str | None = None,
        tag_value: str | None = None,
        kernel_commit: str | None = None,
        hdl_commit: str | None = None,
        limit: int = 50,
    ) -> list[TestRun]:
        stmt = select(TestRun).where(TestRun.project_id == project_id)
        if status:
            stmt = stmt.where(TestRun.status == RunStatus(status))
        if tag_key is not None and tag_value is not None:
            stmt = stmt.join(RunTag, RunTag.run_id == TestRun.id).where(
                RunTag.key == tag_key, RunTag.value == tag_value
            )
        if kernel_commit is not None:
            stmt = stmt.where(
                TestRun.id.in_(
                    select(LogReport.run_id).where(LogReport.kernel_commit == kernel_commit)
                )
            )
        if hdl_commit is not None:
            stmt = stmt.where(
                TestRun.id.in_(select(LogReport.run_id).where(LogReport.hdl_commit == hdl_commit))
            )
        stmt = stmt.order_by(TestRun.created_at.desc()).limit(limit)
        return list(self._session.execute(stmt).scalars())

    def runs_with_boot_log(self, run_ids: list[str]) -> set[str]:
        """Return the subset of run_ids that have at least one parsed boot log."""
        if not run_ids:
            return set()
        rows = self._session.execute(
            select(LogReport.run_id)
            .where(LogReport.run_id.in_(run_ids))
            .where(
                ~LogReport.source.ilike("%terminal%"),
                ~LogReport.source.ilike("%console%"),
                ~LogReport.source.ilike("%stdout%"),
                ~LogReport.source.ilike("%stderr%"),
            )
            .distinct()
        ).scalars()
        return set(rows)

    def runs_with_terminal_log(self, run_ids: list[str]) -> set[str]:
        """Return the subset of run_ids that have at least one parsed terminal log."""
        if not run_ids:
            return set()
        rows = self._session.execute(
            select(LogReport.run_id)
            .where(LogReport.run_id.in_(run_ids))
            .where(
                (LogReport.source.ilike("%terminal%"))
                | (LogReport.source.ilike("%console%"))
                | (LogReport.source.ilike("%stdout%"))
                | (LogReport.source.ilike("%stderr%"))
            )
            .distinct()
        ).scalars()
        return set(rows)

    def runs_with_figures(self, run_ids: list[str]) -> set[str]:
        """Return the subset of run_ids that own at least one figure artifact.

        Figure artifacts (``FIGURE_KINDS``) may be attached at run, suite, or case
        scope via the polymorphic ``Artifact.owner_type``/``owner_id`` pair, so we
        resolve each owner back to its run. Three batched queries, independent of
        the number of runs.
        """
        if not run_ids:
            return set()

        suite_rows = self._session.execute(
            select(TestSuite.id, TestSuite.run_id).where(TestSuite.run_id.in_(run_ids))
        ).all()
        suite_to_run: dict[str, str] = {}
        for suite_id, owning_run_id in suite_rows:
            suite_to_run[suite_id] = owning_run_id

        case_to_run: dict[str, str] = {}
        if suite_to_run:
            case_rows = self._session.execute(
                select(TestCase.id, TestCase.suite_id).where(
                    TestCase.suite_id.in_(list(suite_to_run))
                )
            ).all()
            case_to_run = {cid: suite_to_run[sid] for cid, sid in case_rows}

        owner_ids = list(run_ids) + list(suite_to_run) + list(case_to_run)
        art_rows = self._session.execute(
            select(Artifact.owner_type, Artifact.owner_id).where(
                Artifact.kind.in_(FIGURE_KINDS), Artifact.owner_id.in_(owner_ids)
            )
        ).all()

        run_id_set = set(run_ids)
        result: set[str] = set()
        for owner_type, owner_id in art_rows:
            if owner_type == "run" and owner_id in run_id_set:
                result.add(owner_id)
            elif owner_type == "suite" and owner_id in suite_to_run:
                result.add(suite_to_run[owner_id])
            elif owner_type == "case" and owner_id in case_to_run:
                result.add(case_to_run[owner_id])
        return result

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
