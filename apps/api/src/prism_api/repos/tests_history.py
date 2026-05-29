"""Per-test history aggregation across a project's runs.

Rows are fetched ordered by run time and grouped/scored in Python so the logic
stays portable across SQLite (tests) and Postgres.
"""

from collections import defaultdict
from itertools import pairwise
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from prism_api.models.run import TestRun
from prism_api.models.suite import TestCase, TestSuite


class TestHistoryRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _rows(
        self, project_id: str, classname: str | None = None, name: str | None = None
    ) -> list[Any]:
        stmt = (
            select(
                TestRun.id,
                TestRun.name,
                TestRun.created_at,
                TestCase.classname,
                TestCase.name,
                TestCase.status,
                TestCase.duration_ms,
            )
            .join(TestSuite, TestSuite.run_id == TestRun.id)
            .join(TestCase, TestCase.suite_id == TestSuite.id)
            .where(TestRun.project_id == project_id)
            .order_by(TestRun.created_at.asc())
        )
        if classname is not None:
            stmt = stmt.where(TestCase.classname == classname)
        if name is not None:
            stmt = stmt.where(TestCase.name == name)
        return list(self._session.execute(stmt).all())

    def aggregate(self, project_id: str, *, recent: int = 15) -> list[dict[str, Any]]:
        """One summary per (classname, name): counts, fail-rate, flaky score."""
        groups: dict[tuple[str, str], list[tuple[str, int]]] = defaultdict(list)
        for _run_id, _run_name, _created, classname, cname, status, dur in self._rows(project_id):
            groups[(classname, cname)].append((str(status), int(dur)))

        out: list[dict[str, Any]] = []
        for (classname, cname), items in groups.items():
            statuses = [s for s, _ in items]
            durations = [d for _, d in items]
            n = len(items)
            passes = sum(1 for s in statuses if s == "pass")
            fails = sum(1 for s in statuses if s in ("fail", "error"))
            skips = sum(1 for s in statuses if s == "skip")
            # Flaky score: pass<->not-pass flips across the ordered, non-skip history.
            seq = [s == "pass" for s in statuses if s != "skip"]
            flaky = sum(1 for a, b in pairwise(seq) if a != b)
            out.append(
                {
                    "classname": classname,
                    "name": cname,
                    "runs": n,
                    "pass_count": passes,
                    "fail_count": fails,
                    "skip_count": skips,
                    "fail_rate": fails / n if n else 0.0,
                    "flaky_score": flaky,
                    "last_status": statuses[-1],
                    "avg_duration_ms": sum(durations) / n if n else 0.0,
                    "last_duration_ms": durations[-1] if durations else 0,
                    "recent_statuses": statuses[-recent:],
                }
            )
        out.sort(key=lambda t: (-t["flaky_score"], -t["fail_rate"], t["classname"], t["name"]))
        return out

    def timeline(self, project_id: str, classname: str, name: str) -> list[dict[str, Any]]:
        """Per-run timeline for one test, oldest->newest."""
        return [
            {
                "run_id": run_id,
                "run_name": run_name,
                "created_at": created,
                "status": str(status),
                "duration_ms": int(dur),
            }
            for run_id, run_name, created, _cn, _nm, status, dur in self._rows(
                project_id, classname, name
            )
        ]
