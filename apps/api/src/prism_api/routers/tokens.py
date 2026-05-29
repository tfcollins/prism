"""Per-user API tokens for programmatic access (CI uploads, scripts)."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from prism_api.deps import csrf_protect, current_user, session_dep
from prism_api.models.api_token import ApiToken
from prism_api.models.user import User
from prism_api.repos.audit import AuditRepo
from prism_api.repos.tokens import TokenRepo
from prism_api.schemas.token import CreateTokenRequest, TokenCreatedOut, TokenOut
from prism_api.tokens import display_prefix, generate_token, hash_token

router = APIRouter(prefix="/api/v1/tokens", tags=["tokens"])


def _to_out(t: ApiToken) -> TokenOut:
    return TokenOut(
        id=t.id,
        name=t.name,
        prefix=t.prefix,
        created_at=t.created_at,
        last_used_at=t.last_used_at,
        expires_at=t.expires_at,
    )


@router.get("")
def list_tokens(
    user: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[TokenOut]:
    return [_to_out(t) for t in TokenRepo(session).list_for_user(user.id)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_token(
    body: CreateTokenRequest,
    user: User = Depends(current_user),
    _csrf: None = Depends(csrf_protect),
    session: Session = Depends(session_dep),
) -> TokenCreatedOut:
    raw = generate_token()
    expires_at = (
        datetime.now(UTC) + timedelta(days=body.expires_in_days)
        if body.expires_in_days is not None
        else None
    )
    token = TokenRepo(session).create(
        user_id=user.id,
        name=body.name,
        token_hash=hash_token(raw),
        prefix=display_prefix(raw),
        expires_at=expires_at,
    )
    AuditRepo(session).record(
        user_id=user.id,
        action="token.create",
        target_type="token",
        target_id=token.id,
        detail={"name": token.name},
    )
    out = _to_out(token)
    return TokenCreatedOut(token=raw, **out.model_dump())


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_token(
    token_id: str,
    user: User = Depends(current_user),
    _csrf: None = Depends(csrf_protect),
    session: Session = Depends(session_dep),
) -> Response:
    repo = TokenRepo(session)
    token = repo.get_for_user(token_id, user.id)
    if token is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "token not found")
    repo.delete(token)
    AuditRepo(session).record(
        user_id=user.id,
        action="token.revoke",
        target_type="token",
        target_id=token_id,
        detail={"name": token.name},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
