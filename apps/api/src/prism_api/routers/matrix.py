"""Matrix dashboard endpoints: read grid + admin config."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from prism_api.deps import csrf_protect, current_user, require_admin, session_dep
from prism_api.models.user import User
from prism_api.repos.matrix import MatrixRepo
from prism_api.repos.matrix_config import MatrixConfigRepo
from prism_api.schemas.matrix import MatrixConfigBody, MatrixConfigOut, MatrixResponse

router = APIRouter(prefix="/api/v1/matrix", tags=["matrix"])


@router.get("")
def get_matrix(
    scope: str,
    boot_file: Annotated[list[str] | None, Query()] = None,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> MatrixResponse:
    config = MatrixConfigRepo(session).effective(scope)
    result = MatrixRepo(session).compute(
        scope=scope, boot_files=boot_file or [], config=config
    )
    return MatrixResponse(**result)


@router.get("/config")
def get_config(
    scope: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> MatrixConfigOut:
    config = MatrixConfigRepo(session).effective(scope)
    return MatrixConfigOut(scope=scope, config=config)


@router.put("/config", dependencies=[Depends(csrf_protect), Depends(require_admin)])
def put_config(
    scope: str,
    body: MatrixConfigBody,
    session: Session = Depends(session_dep),
) -> MatrixConfigOut:
    repo = MatrixConfigRepo(session)
    row = repo.upsert(scope, body.model_dump())
    return MatrixConfigOut(scope=scope, config=row.config)
