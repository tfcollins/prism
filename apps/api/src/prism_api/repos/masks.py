"""Spectrum mask repository."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from prism_api.models.mask import SpectrumMask


class MaskRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, project_id: str, name: str, segments: list[dict[str, Any]]) -> SpectrumMask:
        mask = SpectrumMask(project_id=project_id, name=name, segments=segments)
        self._session.add(mask)
        self._session.flush()
        return mask

    def list_by_project(self, project_id: str) -> list[SpectrumMask]:
        return list(
            self._session.execute(
                select(SpectrumMask)
                .where(SpectrumMask.project_id == project_id)
                .order_by(SpectrumMask.name)
            ).scalars()
        )

    def get(self, mask_id: str) -> SpectrumMask | None:
        return self._session.get(SpectrumMask, mask_id)

    def delete(self, mask_id: str) -> None:
        mask = self._session.get(SpectrumMask, mask_id)
        if mask is not None:
            self._session.delete(mask)
