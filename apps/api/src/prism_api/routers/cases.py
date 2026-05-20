from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from prism_api.deps import current_user, session_dep
from prism_api.models.user import User
from prism_api.repos.artifacts import ArtifactRepo
from prism_api.repos.specs import SpecRepo
from prism_api.repos.suites import MeasurementRepo
from prism_api.schemas.case import (
    CaseArtifactOut,
    CaseDetail,
    MeasurementOut,
    measurement_margin,
)
from prism_api.schemas.spec import resolve_spec

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])


@router.get("/{case_id}", response_model=CaseDetail)
def get_case(
    case_id: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> CaseDetail:
    # CaseRepo doesn't have get_by_id — fetch directly
    from prism_api.models.run import TestRun
    from prism_api.models.suite import TestCase, TestSuite

    case = session.get(TestCase, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case not found")
    artifacts = [
        CaseArtifactOut(id=a.id, kind=a.kind.value, filename=a.filename, size_bytes=a.size_bytes)
        for a in ArtifactRepo(session).list_by_owner("case", case.id)
    ]
    suite = session.get(TestSuite, case.suite_id)
    run = session.get(TestRun, suite.run_id) if suite else None
    spec_map = SpecRepo(session).map_for_project(run.project_id) if run else {}
    measurements = []
    for m in MeasurementRepo(session).list_by_case(case.id):
        ps = spec_map.get(m.name)
        smin, smax = resolve_spec(
            m.spec_min, m.spec_max, ps.spec_min if ps else None, ps.spec_max if ps else None
        )
        margin = measurement_margin(m.value, smin, smax)
        measurements.append(
            MeasurementOut(
                name=m.name,
                value=m.value,
                unit=m.unit,
                spec_min=smin,
                spec_max=smax,
                in_spec=None if margin is None else margin >= 0,
                margin=margin,
            )
        )
    return CaseDetail(
        id=case.id,
        suite_id=case.suite_id,
        classname=case.classname,
        name=case.name,
        status=case.status.value,
        duration_ms=case.duration_ms,
        failure_message=case.failure_message,
        failure_trace=case.failure_trace,
        artifacts=artifacts,
        measurements=measurements,
    )
