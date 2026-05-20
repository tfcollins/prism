"""Saved-view repository."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from prism_api.models.view import SavedView


class ViewRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_by_project(self, project_id: str) -> list[SavedView]:
        return list(
            self._session.execute(
                select(SavedView).where(SavedView.project_id == project_id).order_by(SavedView.name)
            ).scalars()
        )

    def get(self, project_id: str, name: str) -> SavedView | None:
        return self._session.execute(
            select(SavedView).where(SavedView.project_id == project_id, SavedView.name == name)
        ).scalar_one_or_none()

    def upsert(self, *, project_id: str, name: str, config: dict[str, Any]) -> SavedView:
        existing = self.get(project_id, name)
        if existing is not None:
            existing.config = config
            return existing
        view = SavedView(project_id=project_id, name=name, config=config)
        self._session.add(view)
        self._session.flush()
        return view

    def delete(self, project_id: str, name: str) -> bool:
        existing = self.get(project_id, name)
        if existing is None:
            return False
        self._session.delete(existing)
        return True
