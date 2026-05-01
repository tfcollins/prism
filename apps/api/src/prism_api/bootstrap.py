"""Bootstrap helpers — runs on app startup."""

from sqlalchemy.orm import Session

from prism_api.auth import hash_password
from prism_api.repos.users import UserRepo


def ensure_bootstrap_admin(session: Session, *, email: str | None, password: str | None) -> None:
    """Create the bootstrap admin if no users exist and credentials are provided."""
    if not email or not password:
        return
    repo = UserRepo(session)
    if repo.list_all():
        return
    repo.create(email=email, password_hash=hash_password(password))
