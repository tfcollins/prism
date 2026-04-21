"""User management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from prism_api.auth import hash_password
from prism_api.deps import current_user, session_dep
from prism_api.models.user import User
from prism_api.repos.users import UserRepo
from prism_api.schemas.user import CreateUserRequest, UserOut

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("")
def list_users(
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[UserOut]:
    return [UserOut(id=u.id, email=u.email) for u in UserRepo(session).list_all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    body: CreateUserRequest,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> UserOut:
    try:
        user = UserRepo(session).create(
            email=body.email, password_hash=hash_password(body.password)
        )
        session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "email already exists") from exc
    return UserOut(id=user.id, email=user.email)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    current: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> Response:
    repo = UserRepo(session)
    if current.id == user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot delete yourself")
    target = repo.get_by_id(user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    total = len(repo.list_all())
    if total <= 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot delete the last remaining user")
    repo.delete(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
