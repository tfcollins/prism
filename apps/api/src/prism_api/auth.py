"""Password hashing and JWT helpers."""
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


class InvalidTokenError(Exception):
    """Raised when a JWT cannot be decoded or is expired."""


@dataclass(frozen=True)
class TokenClaims:
    subject: str
    expires_at: datetime


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


def create_access_token(
    *,
    subject: str,
    secret: str,
    ttl: timedelta,
    algorithm: str = "HS256",
) -> str:
    expires_at = datetime.now(UTC) + ttl
    payload = {"sub": subject, "exp": int(expires_at.timestamp())}
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_access_token(token: str, *, secret: str, algorithm: str = "HS256") -> TokenClaims:
    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
    except JWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
    sub = payload.get("sub")
    exp = payload.get("exp")
    if not isinstance(sub, str) or not isinstance(exp, int):
        raise InvalidTokenError("malformed claims")
    return TokenClaims(subject=sub, expires_at=datetime.fromtimestamp(exp, tz=UTC))
