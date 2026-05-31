"""Global search endpoint."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from prism_api.deps import current_user, session_dep
from prism_api.models.user import User
from prism_api.repos.search import SearchRepo
from prism_api.schemas.search import SearchHit

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("")
def search(
    q: str = Query(default="", description="search text"),
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[SearchHit]:
    query = q.strip()
    if len(query) < 2:
        return []
    return [SearchHit.model_validate(h) for h in SearchRepo(session).search(query)]
