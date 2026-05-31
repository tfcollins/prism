"""Flat per-case (+ measurement) rows for CSV export."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from prism_api.models.run import TestRun
from prism_api.models.suite import Measurement, TestCase, TestSuite

EXPORT_COLUMNS = [
    "run_name",
    "run_status",
    "created_at",
    "suite",
    "classname",
    "case_name",
    "case_status",
    "duration_ms",
    "measurement",
    "value",
    "unit",
    "spec_min",
    "spec_max",
]


class ExportRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def rows(self, project_id: str) -> list[tuple[Any, ...]]:
        """Every case in the project, left-joined to its measurements."""
        stmt = (
            select(
                TestRun.name,
                TestRun.status,
                TestRun.created_at,
                TestSuite.name,
                TestCase.classname,
                TestCase.name,
                TestCase.status,
                TestCase.duration_ms,
                Measurement.name,
                Measurement.value,
                Measurement.unit,
                Measurement.spec_min,
                Measurement.spec_max,
            )
            .select_from(TestCase)
            .join(TestSuite, TestSuite.id == TestCase.suite_id)
            .join(TestRun, TestRun.id == TestSuite.run_id)
            .outerjoin(Measurement, Measurement.case_id == TestCase.id)
            .where(TestRun.project_id == project_id)
            .order_by(TestRun.created_at, TestSuite.name, TestCase.name, Measurement.name)
        )
        return [tuple(r) for r in self._session.execute(stmt).all()]
