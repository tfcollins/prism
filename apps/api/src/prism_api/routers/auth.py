"""Auth endpoints."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from prism_api.auth import create_access_token, verify_password
from prism_api.config import Settings
from prism_api.deps import SESSION_COOKIE, current_user, get_settings_dep, session_dep
from prism_api.models.user import User
from prism_api.repos.users import UserRepo
from prism_api.schemas.auth import LoginRequest, UserOut

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login")
def login(
    body: LoginRequest,
    response: Response,
    settings: Settings = Depends(get_settings_dep),
    session: Session = Depends(session_dep),
) -> UserOut:
    user = UserRepo(session).get_by_email(body.email)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    token = create_access_token(
        subject=user.id,
        secret=settings.jwt_secret,
        ttl=timedelta(minutes=settings.jwt_ttl_minutes),
        algorithm=settings.jwt_algorithm,
    )
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        max_age=settings.jwt_ttl_minutes * 60,
        path="/",
    )
    return UserOut(id=user.id, email=user.email)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, settings: Settings = Depends(get_settings_dep)) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
    )


@router.get("/me")
def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut(id=user.id, email=user.email)
