"""FastAPI dependencies."""
from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from prism_api.auth import InvalidTokenError, decode_access_token
from prism_api.config import Settings, get_settings
from prism_api.db import session_scope
from prism_api.models.user import User
from prism_api.repos.users import UserRepo

SESSION_COOKIE = "prism_session"


def get_settings_dep() -> Settings:
    return get_settings()


def session_dep() -> Iterator[Session]:
    with session_scope() as s:
        yield s


def current_user(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
    session: Session = Depends(session_dep),
) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing session")
    try:
        claims = decode_access_token(token, secret=settings.jwt_secret, algorithm=settings.jwt_algorithm)
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    user = UserRepo(session).get_by_id(claims.subject)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user no longer exists")
    return user
