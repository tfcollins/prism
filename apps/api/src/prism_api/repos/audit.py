"""Audit-event repository."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from prism_api.models.audit import AuditEvent


class AuditRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        *,
        user_id: str | None,
        action: str,
        project_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            user_id=user_id,
            action=action,
            project_id=project_id,
            target_type=target_type,
            target_id=target_id,
            detail=detail or {},
        )
        self._session.add(event)
        return event

    def list_for_project(self, project_id: str, limit: int = 100) -> list[AuditEvent]:
        return list(
            self._session.execute(
                select(AuditEvent)
                .where(AuditEvent.project_id == project_id)
                .order_by(AuditEvent.created_at.desc())
                .limit(limit)
            ).scalars()
        )
