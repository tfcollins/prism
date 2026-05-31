"""Global search across projects, runs, test cases, and boot-log commits.

Uses a portable case-insensitive ``LIKE`` (lower(col) LIKE %q%) so it works on
both SQLite (tests) and Postgres; results are capped per kind.
"""

from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from prism_api.models.log import LogReport
from prism_api.models.project import Project
from prism_api.models.run import TestRun
from prism_api.models.suite import TestCase, TestSuite


def _like(col: Any, needle: str) -> ColumnElement[bool]:
    esc = needle.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return func.lower(col).like(f"%{esc}%", escape="\\")


class SearchRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def search(self, q: str, *, per_kind: int = 8) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []

        for slug, name in self._session.execute(
            select(Project.slug, Project.name)
            .where(_like(Project.name, q) | _like(Project.slug, q))
            .order_by(Project.slug)
            .limit(per_kind)
        ):
            hits.append({"kind": "project", "title": name, "subtitle": slug, "project_slug": slug})

        for rid, rname, status, slug in self._session.execute(
            select(TestRun.id, TestRun.name, TestRun.status, Project.slug)
            .join(Project, Project.id == TestRun.project_id)
            .where(_like(TestRun.name, q))
            .order_by(TestRun.created_at.desc())
            .limit(per_kind)
        ):
            hits.append(
                {
                    "kind": "run",
                    "title": rname,
                    "subtitle": f"{slug} · {status}",
                    "project_slug": slug,
                    "run_id": rid,
                }
            )

        for cname, classname, rid, slug in self._session.execute(
            select(TestCase.name, TestCase.classname, TestRun.id, Project.slug)
            .join(TestSuite, TestSuite.id == TestCase.suite_id)
            .join(TestRun, TestRun.id == TestSuite.run_id)
            .join(Project, Project.id == TestRun.project_id)
            .where(
                _like(TestCase.name, q)
                | _like(TestCase.classname, q)
                | _like(TestCase.failure_message, q)
            )
            .order_by(TestRun.created_at.desc())
            .limit(per_kind)
        ):
            hits.append(
                {
                    "kind": "case",
                    "title": cname,
                    "subtitle": f"{classname} · {slug}" if classname else slug,
                    "project_slug": slug,
                    "run_id": rid,
                }
            )

        seen_commits: set[str] = set()
        for kernel, hdl, rid, slug in self._session.execute(
            select(LogReport.kernel_commit, LogReport.hdl_commit, LogReport.run_id, Project.slug)
            .join(TestRun, TestRun.id == LogReport.run_id)
            .join(Project, Project.id == TestRun.project_id)
            .where(_like(LogReport.kernel_commit, q) | _like(LogReport.hdl_commit, q))
            .order_by(LogReport.created_at.desc())
            .limit(per_kind * 2)
        ):
            for label, commit in (("kernel", kernel), ("hdl", hdl)):
                if commit and q.lower() in commit.lower() and commit not in seen_commits:
                    seen_commits.add(commit)
                    hits.append(
                        {
                            "kind": "commit",
                            "title": commit[:12],
                            "subtitle": f"{label} commit · {slug}",
                            "project_slug": slug,
                            "run_id": rid,
                        }
                    )
                    if len([h for h in hits if h["kind"] == "commit"]) >= per_kind:
                        break

        return hits
