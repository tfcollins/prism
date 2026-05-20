"""Spec-definition repository."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from prism_api.models.spec import SpecDefinition


class SpecRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_by_project(self, project_id: str) -> list[SpecDefinition]:
        return list(
            self._session.execute(
                select(SpecDefinition)
                .where(SpecDefinition.project_id == project_id)
                .order_by(SpecDefinition.measurement_name)
            ).scalars()
        )

    def map_for_project(self, project_id: str) -> dict[str, SpecDefinition]:
        return {s.measurement_name: s for s in self.list_by_project(project_id)}

    def get(self, project_id: str, measurement_name: str) -> SpecDefinition | None:
        return self._session.execute(
            select(SpecDefinition).where(
                SpecDefinition.project_id == project_id,
                SpecDefinition.measurement_name == measurement_name,
            )
        ).scalar_one_or_none()

    def upsert(
        self,
        *,
        project_id: str,
        measurement_name: str,
        spec_min: float | None,
        spec_max: float | None,
        unit: str | None,
    ) -> SpecDefinition:
        existing = self.get(project_id, measurement_name)
        if existing is not None:
            existing.spec_min = spec_min
            existing.spec_max = spec_max
            existing.unit = unit
            return existing
        spec = SpecDefinition(
            project_id=project_id,
            measurement_name=measurement_name,
            spec_min=spec_min,
            spec_max=spec_max,
            unit=unit,
        )
        self._session.add(spec)
        self._session.flush()
        return spec

    def delete(self, project_id: str, measurement_name: str) -> bool:
        existing = self.get(project_id, measurement_name)
        if existing is None:
            return False
        self._session.delete(existing)
        return True
