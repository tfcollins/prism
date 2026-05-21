# apps/api/src/prism_api/repos/logs.py
"""Log-report repository + commit cross-reference queries."""

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from prism_api.models.log import LogFinding, LogReport
from prism_api.models.run import TestRun
from prism_api.parsers.logs import ParsedLog

_COMMIT_COL = {"kernel": LogReport.kernel_commit, "hdl": LogReport.hdl_commit}


class LogRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_report(
        self, *, run_id: str, artifact_id: str | None, source: str, parsed: ParsedLog
    ) -> LogReport:
        report = LogReport(
            run_id=run_id,
            artifact_id=artifact_id,
            source=source,
            kernel_version=parsed.kernel_version,
            board=parsed.board,
            kernel_commit=parsed.kernel_commit,
            hdl_commit=parsed.hdl_commit,
            error_count=parsed.error_count,
            warn_count=parsed.warn_count,
            has_panic=parsed.has_panic,
        )
        self._session.add(report)
        self._session.flush()
        for f in parsed.findings:
            self._session.add(
                LogFinding(
                    log_report_id=report.id, severity=f.severity, line_no=f.line_no, text=f.text
                )
            )
        self._session.flush()
        return report

    def list_by_run(self, run_id: str) -> list[LogReport]:
        return list(
            self._session.execute(
                select(LogReport).where(LogReport.run_id == run_id).order_by(LogReport.created_at)
            ).scalars()
        )

    def findings_for(self, report_id: str) -> list[LogFinding]:
        return list(
            self._session.execute(
                select(LogFinding)
                .where(LogFinding.log_report_id == report_id)
                .order_by(LogFinding.line_no)
            ).scalars()
        )

    def commit_counts(self, kind: str) -> list[tuple[str, int]]:
        """Distinct commits (of `kind`) within a join scope = all runs; callers
        filter by project via run join. Returns (commit, distinct-run-count)."""
        col = _COMMIT_COL[kind]
        rows = self._session.execute(
            select(col, func.count(distinct(LogReport.run_id)))
            .where(col.is_not(None))
            .group_by(col)
            .order_by(col)
        ).all()
        return [(str(c), int(n)) for c, n in rows]

    def commit_counts_for_project(self, kind: str, project_id: str) -> list[tuple[str, int]]:
        col = _COMMIT_COL[kind]
        rows = self._session.execute(
            select(col, func.count(distinct(LogReport.run_id)))
            .join(TestRun, TestRun.id == LogReport.run_id)
            .where(col.is_not(None), TestRun.project_id == project_id)
            .group_by(col)
            .order_by(col)
        ).all()
        return [(str(c), int(n)) for c, n in rows]

    def run_ids_for_commit(self, kind: str, commit: str) -> set[str]:
        col = _COMMIT_COL[kind]
        rows = self._session.execute(
            select(distinct(LogReport.run_id)).where(col == commit)
        ).scalars()
        return set(rows)

    def shared_count(self, kind: str, commit: str, *, exclude_run_id: str) -> int:
        return len(self.run_ids_for_commit(kind, commit) - {exclude_run_id})
