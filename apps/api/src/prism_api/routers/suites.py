from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from prism_api.deps import current_user, session_dep
from prism_api.models.user import User
from prism_api.repos.suites import CaseRepo


class CaseListItem(BaseModel):
    id: str
    classname: str
    name: str
    status: str
    duration_ms: int


router = APIRouter(prefix="/api/v1/suites", tags=["suites"])


@router.get("/{suite_id}/cases", response_model=list[CaseListItem])
def list_cases(
    suite_id: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[CaseListItem]:
    return [
        CaseListItem(id=c.id, classname=c.classname, name=c.name, status=c.status.value, duration_ms=c.duration_ms)
        for c in CaseRepo(session).list_by_suite(suite_id)
    ]
