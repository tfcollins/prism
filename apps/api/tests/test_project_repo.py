"""Project repository tests."""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from prism_api.models import Base
from prism_api.repos.projects import ProjectRepo


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        yield s
    engine.dispose()


def test_create_and_lookup(session: Session) -> None:
    repo = ProjectRepo(session)
    p = repo.create(slug="audio", name="Audio", description="hi")
    session.commit()
    assert repo.get_by_slug("audio") == p


def test_list_projects(session: Session) -> None:
    repo = ProjectRepo(session)
    repo.create(slug="a", name="A")
    repo.create(slug="b", name="B")
    session.commit()
    assert [p.slug for p in repo.list_all()] == ["a", "b"]


def test_delete(session: Session) -> None:
    repo = ProjectRepo(session)
    p = repo.create(slug="a", name="A")
    session.commit()
    repo.delete(p.id)
    session.commit()
    assert repo.get_by_slug("a") is None
