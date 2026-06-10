"""Matrix dashboard computation: latest run per (row, col) cell."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from prism_api.models.project import Project
from prism_api.models.run import RunStatus, RunTag, TestRun
from prism_api.repos.runs import RunRepo

RELEASE_TAG_KEY = "kuiper-linux-release"


class MatrixRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _candidate_runs(self, scope: str) -> list[TestRun]:
        if scope == "global":
            sub = select(RunTag.run_id).where(RunTag.key == RELEASE_TAG_KEY)
            stmt = select(TestRun).where(TestRun.id.in_(sub))
            return list(self._session.execute(stmt).scalars())
        if scope.startswith("project:"):
            slug = scope.split(":", 1)[1]
            proj = self._session.execute(
                select(Project).where(Project.slug == slug)
            ).scalar_one_or_none()
            if proj is None:
                return []
            stmt = select(TestRun).where(TestRun.project_id == proj.id)
            return list(self._session.execute(stmt).scalars())
        return []

    def _tags_by_run(self, run_ids: list[str], keys: list[str]) -> dict[str, dict[str, str]]:
        if not run_ids:
            return {}
        rows = self._session.execute(
            select(RunTag.run_id, RunTag.key, RunTag.value).where(
                RunTag.run_id.in_(run_ids), RunTag.key.in_(keys)
            )
        ).all()
        out: dict[str, dict[str, str]] = {}
        for run_id, key, value in rows:
            out.setdefault(run_id, {})[key] = value
        return out

    @staticmethod
    def _as_utc(dt: datetime) -> datetime:
        """Normalise to UTC-aware; SQLite strips tzinfo on read, so treat naive as UTC."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt

    @staticmethod
    def _sort_key(run: TestRun) -> tuple[datetime, datetime, str]:
        finished = MatrixRepo._as_utc(run.finished_at or run.created_at)
        return (finished, MatrixRepo._as_utc(run.created_at), run.id)

    def compute(
        self, *, scope: str, boot_files: list[str], config: dict[str, Any]
    ) -> dict[str, Any]:
        row_key = config["row_key"]
        col_key = config["col_key"]
        filter_key = config["filter_key"]
        stale_after_hours = int(config["stale_after_hours"])

        runs = self._candidate_runs(scope)
        # Ignore runs that never completed.
        runs = [r for r in runs if r.status != RunStatus.PENDING]
        tags = self._tags_by_run([r.id for r in runs], [row_key, col_key, filter_key])

        # Available boot-file values (before applying the filter) for the filter bar.
        boot_file_values = sorted(
            v for v in {tags.get(r.id, {}).get(filter_key) for r in runs} if v is not None
        )

        # Apply boot-file filter.
        if boot_files:
            wanted = set(boot_files)
            runs = [r for r in runs if tags.get(r.id, {}).get(filter_key) in wanted]

        # Split placeable vs unplaced.
        placeable: list[TestRun] = []
        unplaced = 0
        for r in runs:
            t = tags.get(r.id, {})
            if t.get(row_key) and t.get(col_key):
                placeable.append(r)
            else:
                unplaced += 1

        # Latest run per (row, col).
        latest: dict[tuple[str, str], TestRun] = {}
        for r in sorted(placeable, key=self._sort_key, reverse=True):
            t = tags[r.id]
            cellkey = (t[row_key], t[col_key])
            if cellkey not in latest:
                latest[cellkey] = r

        observed_rows = {k[0] for k in latest}
        observed_cols = {k[1] for k in latest}
        rows = sorted(observed_rows | set(config.get("curated_rows", [])))
        cols = sorted(observed_cols | set(config.get("curated_cols", [])))

        now = datetime.now(UTC)
        run_repo = RunRepo(self._session)
        cells: dict[str, dict[str, Any]] = {}
        # NOTE: one aggregate query per occupied cell (N+1). Acceptable at lab
        # scale (tens of cells), matching the overview/runs pattern. Revisit with
        # a bulk query if cell counts grow large.
        for (rv, cv), run in latest.items():
            counts = run_repo.aggregate_counts_by_run(run.id)
            total = (
                counts["pass_count"]
                + counts["fail_count"]
                + counts["error_count"]
                + counts["skip_count"]
            )
            finished = self._as_utc(run.finished_at or run.created_at)
            age_seconds = int((now - finished).total_seconds())
            cells[f"{rv}|{cv}"] = {
                "status": str(run.status),
                "run_id": run.id,
                "passed": counts["pass_count"],
                "total": total,
                "finished_at": run.finished_at,
                "age_seconds": age_seconds,
                "stale": age_seconds > stale_after_hours * 3600,
            }

        summary = {"pass": 0, "fail": 0, "mixed": 0, "error": 0, "no_run": 0}
        for rv in rows:
            for cv in cols:
                cell = cells.get(f"{rv}|{cv}")
                if cell is None:
                    summary["no_run"] += 1
                else:
                    summary[cell["status"]] = summary.get(cell["status"], 0) + 1

        return {
            "scope": scope,
            "generated_at": now,
            "row_key": row_key,
            "col_key": col_key,
            "rows": rows,
            "cols": cols,
            "boot_files": boot_file_values,
            "stale_after_hours": stale_after_hours,
            "summary": summary,
            "unplaced_runs": unplaced,
            "cells": cells,
        }
