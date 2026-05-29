"""Model smoke tests against in-memory SQLite."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from prism_api.models import Base
from prism_api.models.project import Project
from prism_api.models.user import User


def test_create_user_and_project() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        user = User(email="a@b.com", password_hash="x")
        project = Project(slug="audio", name="Audio Codec", description="d")
        session.add_all([user, project])
        session.commit()
        assert user.id is not None
        assert project.id is not None
        assert project.slug == "audio"
    engine.dispose()
