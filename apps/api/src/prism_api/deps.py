"""FastAPI dependencies."""

import secrets
from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from prism_api.auth import InvalidTokenError, decode_access_token
from prism_api.config import Settings, get_settings
from prism_api.db import session_scope
from prism_api.models.user import User
from prism_api.repos.tokens import TokenRepo
from prism_api.repos.users import UserRepo
from prism_api.tokens import hash_token

SESSION_COOKIE = "prism_session"
CSRF_COOKIE = "prism_csrf"
CSRF_HEADER = "x-prism-csrf"


def _bearer_token(request: Request) -> str | None:
    auth = request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return None


def issue_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_protect(request: Request) -> None:
    # Bearer (API-token) auth is not cookie-based, so CSRF doesn't apply.
    if _bearer_token(request) is not None:
        return
    cookie_token = request.cookies.get(CSRF_COOKIE)
    header_token = request.headers.get(CSRF_HEADER)
    if (
        not cookie_token
        or not header_token
        or not secrets.compare_digest(cookie_token, header_token)
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "missing or invalid csrf token")


def get_settings_dep() -> Settings:
    return get_settings()


def session_dep() -> Iterator[Session]:
    with session_scope() as s:
        yield s


def _user_from_bearer(raw: str, session: Session) -> User:
    """Resolve a Bearer API token to its user, or raise 401."""
    rec = TokenRepo(session).get_by_hash(hash_token(raw)) if raw else None
    if rec is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired API token")
    if rec.expires_at is not None:
        exp = rec.expires_at if rec.expires_at.tzinfo else rec.expires_at.replace(tzinfo=UTC)
        if exp < datetime.now(UTC):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired API token")
    rec.last_used_at = datetime.now(UTC)  # committed by session_scope at request end
    user = session.get(User, rec.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token owner no longer exists")
    return user


def current_user(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
    session: Session = Depends(session_dep),
) -> User:
    bearer = _bearer_token(request)
    if bearer is not None:
        return _user_from_bearer(bearer, session)
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing session")
    try:
        claims = decode_access_token(
            token, secret=settings.jwt_secret, algorithm=settings.jwt_algorithm
        )
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    user = UserRepo(session).get_by_id(claims.subject)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user no longer exists")
    return user


def is_admin_user(user: User, settings: Settings) -> bool:
    """The bootstrap admin (ADMIN_EMAIL) is the sole admin. No stored role."""
    return bool(settings.admin_email) and user.email == settings.admin_email


def require_admin(
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings_dep),
) -> User:
    """Gate admin-only endpoints to the bootstrap admin account."""
    if not is_admin_user(user, settings):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin access required")
    return user
