"""Suite and case repositories."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from prism_api.models.run import TestRun
from prism_api.models.suite import CaseStatus, Measurement, TestCase, TestSuite


class SuiteRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        run_id: str,
        name: str,
        pass_count: int = 0,
        fail_count: int = 0,
        error_count: int = 0,
        skip_count: int = 0,
        duration_ms: int = 0,
    ) -> TestSuite:
        suite = TestSuite(
            run_id=run_id,
            name=name,
            pass_count=pass_count,
            fail_count=fail_count,
            error_count=error_count,
            skip_count=skip_count,
            duration_ms=duration_ms,
        )
        self._session.add(suite)
        self._session.flush()
        return suite

    def list_by_run(self, run_id: str) -> list[TestSuite]:
        return list(
            self._session.execute(select(TestSuite).where(TestSuite.run_id == run_id)).scalars()
        )


class CaseRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        suite_id: str,
        classname: str,
        name: str,
        status: CaseStatus,
        duration_ms: int = 0,
        failure_message: str | None = None,
        failure_trace: str | None = None,
    ) -> TestCase:
        case = TestCase(
            suite_id=suite_id,
            classname=classname,
            name=name,
            status=status,
            duration_ms=duration_ms,
            failure_message=failure_message,
            failure_trace=failure_trace,
        )
        self._session.add(case)
        self._session.flush()
        return case

    def list_by_suite(self, suite_id: str) -> list[TestCase]:
        return list(
            self._session.execute(select(TestCase).where(TestCase.suite_id == suite_id)).scalars()
        )


class MeasurementRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        case_id: str,
        name: str,
        value: float,
        unit: str | None = None,
        spec_min: float | None = None,
        spec_max: float | None = None,
    ) -> Measurement:
        m = Measurement(
            case_id=case_id,
            name=name,
            value=value,
            unit=unit,
            spec_min=spec_min,
            spec_max=spec_max,
        )
        self._session.add(m)
        self._session.flush()
        return m

    def list_by_case(self, case_id: str) -> list[Measurement]:
        return list(
            self._session.execute(
                select(Measurement).where(Measurement.case_id == case_id)
            ).scalars()
        )

    def list_by_run(self, run_id: str) -> list[Measurement]:
        rows = self._session.execute(
            select(Measurement)
            .join(TestCase, Measurement.case_id == TestCase.id)
            .join(TestSuite, TestCase.suite_id == TestSuite.id)
            .where(TestSuite.run_id == run_id)
            .order_by(Measurement.name)
        ).scalars()
        return list(rows)

    def distinct_names_for_project(self, project_id: str) -> list[str]:
        rows = self._session.execute(
            select(Measurement.name)
            .join(TestCase, Measurement.case_id == TestCase.id)
            .join(TestSuite, TestCase.suite_id == TestSuite.id)
            .join(TestRun, TestSuite.run_id == TestRun.id)
            .where(TestRun.project_id == project_id)
            .distinct()
            .order_by(Measurement.name)
        ).scalars()
        return list(rows)

    def trend_for_project(
        self, project_id: str, name: str
    ) -> list[tuple[Measurement, TestCase, TestRun]]:
        """Measurement occurrences of ``name`` across a project's runs, oldest first."""
        rows = self._session.execute(
            select(Measurement, TestCase, TestRun)
            .join(TestCase, Measurement.case_id == TestCase.id)
            .join(TestSuite, TestCase.suite_id == TestSuite.id)
            .join(TestRun, TestSuite.run_id == TestRun.id)
            .where(TestRun.project_id == project_id, Measurement.name == name)
            .order_by(TestRun.created_at.asc())
        ).all()
        return [(r[0], r[1], r[2]) for r in rows]
