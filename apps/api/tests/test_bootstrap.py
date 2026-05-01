"""Bootstrap admin user tests."""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from prism_api.bootstrap import ensure_bootstrap_admin
from prism_api.models import Base
from prism_api.repos.users import UserRepo


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        yield s


def test_creates_admin_on_empty_db(session: Session) -> None:
    ensure_bootstrap_admin(session, email="admin@x.com", password="p")
    session.commit()
    assert UserRepo(session).get_by_email("admin@x.com") is not None


def test_skipped_when_users_already_exist(session: Session) -> None:
    UserRepo(session).create(email="existing@x.com", password_hash="h")
    session.commit()
    ensure_bootstrap_admin(session, email="admin@x.com", password="p")
    session.commit()
    assert UserRepo(session).get_by_email("admin@x.com") is None


def test_skipped_when_creds_missing(session: Session) -> None:
    ensure_bootstrap_admin(session, email=None, password=None)
    session.commit()
    assert UserRepo(session).list_all() == []
