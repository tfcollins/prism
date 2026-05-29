"""User repository tests against in-memory SQLite."""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from prism_api.models import Base
from prism_api.repos.users import UserRepo


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        yield s
    engine.dispose()


def test_create_and_lookup(session: Session) -> None:
    repo = UserRepo(session)
    user = repo.create(email="a@b.com", password_hash="h")
    session.commit()
    assert repo.get_by_email("a@b.com") == user
    assert repo.get_by_id(user.id) == user


def test_list_users(session: Session) -> None:
    repo = UserRepo(session)
    repo.create(email="a@b.com", password_hash="h")
    repo.create(email="c@d.com", password_hash="h")
    session.commit()
    users = repo.list_all()
    assert {u.email for u in users} == {"a@b.com", "c@d.com"}


def test_delete_user(session: Session) -> None:
    repo = UserRepo(session)
    user = repo.create(email="a@b.com", password_hash="h")
    session.commit()
    repo.delete(user.id)
    session.commit()
    assert repo.get_by_id(user.id) is None
