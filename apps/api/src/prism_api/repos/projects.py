"""Project repository."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from prism_api.models.project import Project


class ProjectRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, slug: str, name: str, description: str = "") -> Project:
        project = Project(slug=slug, name=name, description=description)
        self._session.add(project)
        self._session.flush()
        return project

    def get_by_slug(self, slug: str) -> Project | None:
        return self._session.execute(
            select(Project).where(Project.slug == slug)
        ).scalar_one_or_none()

    def get_by_id(self, project_id: str) -> Project | None:
        return self._session.get(Project, project_id)

    def list_all(self) -> list[Project]:
        return list(
            self._session.execute(select(Project).order_by(Project.created_at)).scalars()
        )

    def delete(self, project_id: str) -> None:
        proj = self._session.get(Project, project_id)
        if proj is not None:
            self._session.delete(proj)
