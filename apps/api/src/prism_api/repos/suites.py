"""Suite and case repositories."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from prism_api.models.suite import CaseStatus, TestCase, TestSuite


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
        return list(self._session.execute(select(TestSuite).where(TestSuite.run_id == run_id)).scalars())


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
        return list(self._session.execute(select(TestCase).where(TestCase.suite_id == suite_id)).scalars())
