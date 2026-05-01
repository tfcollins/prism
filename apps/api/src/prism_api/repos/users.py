"""User repository."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from prism_api.models.user import User


class UserRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, email: str, password_hash: str) -> User:
        user = User(email=email, password_hash=password_hash)
        self._session.add(user)
        self._session.flush()
        return user

    def get_by_id(self, user_id: str) -> User | None:
        return self._session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self._session.execute(select(User).where(User.email == email)).scalar_one_or_none()

    def list_all(self) -> list[User]:
        return list(self._session.execute(select(User).order_by(User.created_at)).scalars())

    def delete(self, user_id: str) -> bool:
        user = self._session.get(User, user_id)
        if user is None:
            return False
        self._session.delete(user)
        return True
