"""Auth endpoints."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from prism_api.auth import create_access_token, verify_password
from prism_api.config import Settings
from prism_api.deps import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    current_user,
    get_settings_dep,
    is_admin_user,
    issue_csrf_token,
    session_dep,
)
from prism_api.ldap_auth import ldap_authenticate
from prism_api.models.user import User
from prism_api.repos.audit import AuditRepo
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
    repo = UserRepo(session)
    existing = repo.get_by_email(body.email)
    user: User | None = None
    # A known local account always authenticates locally — this is what keeps the
    # bootstrap admin usable even when LDAP is enabled or unreachable. Everyone
    # else (unknown email, or an existing LDAP account) goes through LDAP.
    if existing is not None and existing.auth_provider == "local":
        if existing.password_hash and verify_password(body.password, existing.password_hash):
            user = existing
    elif settings.ldap_enabled:
        identity = ldap_authenticate(body.email, body.password, settings)
        if identity is not None:
            user, created = repo.get_or_create_ldap_user(email=identity.email or body.email)
            if created:
                session.commit()  # persist the JIT user so later requests resolve it
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    AuditRepo(session).record(
        user_id=user.id, action="auth.login", detail={"provider": user.auth_provider}
    )
    session.commit()
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
    csrf_token = issue_csrf_token()
    response.set_cookie(
        key=CSRF_COOKIE,
        value=csrf_token,
        httponly=False,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        max_age=settings.jwt_ttl_minutes * 60,
        path="/",
    )
    return UserOut(
        id=user.id,
        email=user.email,
        auth_provider=user.auth_provider,
        is_admin=is_admin_user(user, settings),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, settings: Settings = Depends(get_settings_dep)) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
    )
    response.delete_cookie(
        CSRF_COOKIE, path="/", samesite=settings.cookie_samesite, secure=settings.cookie_secure
    )


@router.get("/me")
def me(
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings_dep),
) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        auth_provider=user.auth_provider,
        is_admin=is_admin_user(user, settings),
    )
