"""API-token repository."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from prism_api.models.api_token import ApiToken


class TokenRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        user_id: str,
        name: str,
        token_hash: str,
        prefix: str,
        expires_at: datetime | None = None,
    ) -> ApiToken:
        token = ApiToken(
            user_id=user_id,
            name=name,
            token_hash=token_hash,
            prefix=prefix,
            expires_at=expires_at,
        )
        self._session.add(token)
        self._session.flush()
        return token

    def list_for_user(self, user_id: str) -> list[ApiToken]:
        return list(
            self._session.execute(
                select(ApiToken)
                .where(ApiToken.user_id == user_id)
                .order_by(ApiToken.created_at.desc())
            ).scalars()
        )

    def get_by_hash(self, token_hash: str) -> ApiToken | None:
        return self._session.execute(
            select(ApiToken).where(ApiToken.token_hash == token_hash)
        ).scalar_one_or_none()

    def get_for_user(self, token_id: str, user_id: str) -> ApiToken | None:
        return self._session.execute(
            select(ApiToken).where(ApiToken.id == token_id, ApiToken.user_id == user_id)
        ).scalar_one_or_none()

    def delete(self, token: ApiToken) -> None:
        self._session.delete(token)
