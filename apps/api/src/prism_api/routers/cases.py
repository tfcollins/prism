from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from prism_api.deps import current_user, session_dep
from prism_api.models.user import User
from prism_api.repos.artifacts import ArtifactRepo
from prism_api.schemas.case import CaseArtifactOut, CaseDetail

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])


@router.get("/{case_id}", response_model=CaseDetail)
def get_case(
    case_id: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> CaseDetail:
    # CaseRepo doesn't have get_by_id — fetch directly
    from prism_api.models.suite import TestCase

    case = session.get(TestCase, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case not found")
    artifacts = [
        CaseArtifactOut(id=a.id, kind=a.kind.value, filename=a.filename, size_bytes=a.size_bytes)
        for a in ArtifactRepo(session).list_by_owner("case", case.id)
    ]
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
    )
