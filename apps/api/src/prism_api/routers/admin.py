"""Admin panel endpoints — restricted to the bootstrap admin account.

Surfaces: user accounts, backup runs (manifests written to object storage by the
backup container), a global activity feed (audit events), and recent container
logs.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from prism_api.config import Settings
from prism_api.deps import get_settings_dep, is_admin_user, require_admin, session_dep
from prism_api.models.project import Project
from prism_api.models.run import TestRun
from prism_api.models.user import User
from prism_api.repos.audit import AuditRepo
from prism_api.repos.projects import ProjectRepo
from prism_api.repos.users import UserRepo
from prism_api.schemas.admin import (
    AccountOut,
    ActivityEventOut,
    AdminProjectOut,
    BackupRunOut,
    ContainerLogsOut,
    ProjectDeletedOut,
)
from prism_api.services.container_logs import read_container_logs
from prism_api.services.retention import delete_project
from prism_api.storage import ObjectStorage, build_storage

# Backup manifests are written here by deploy/backup/backup.sh.
BACKUP_PREFIX = "_backups/"


def _read_backup_manifest(storage: ObjectStorage, key: str) -> BackupRunOut | None:
    """Parse one backup manifest; return None if it's missing/malformed."""
    try:
        return BackupRunOut(**json.loads(storage.get_bytes(key)))
    except Exception:
        return None


router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


@router.get("/accounts")
def list_accounts(
    session: Session = Depends(session_dep),
    settings: Settings = Depends(get_settings_dep),
) -> list[AccountOut]:
    return [
        AccountOut(
            id=u.id,
            email=u.email,
            auth_provider=u.auth_provider,
            is_admin=is_admin_user(u, settings),
            created_at=u.created_at,
        )
        for u in UserRepo(session).list_all()
    ]


@router.get("/activity")
def list_activity(
    limit: int = Query(default=200, ge=1, le=1000),
    session: Session = Depends(session_dep),
) -> list[ActivityEventOut]:
    events = AuditRepo(session).list_recent(limit)
    email_cache: dict[str, str | None] = {}
    out: list[ActivityEventOut] = []
    for e in events:
        email: str | None = None
        if e.user_id is not None:
            if e.user_id not in email_cache:
                u = session.get(User, e.user_id)
                email_cache[e.user_id] = u.email if u else None
            email = email_cache[e.user_id]
        out.append(
            ActivityEventOut(
                action=e.action,
                user_email=email,
                project_id=e.project_id,
                target_type=e.target_type,
                target_id=e.target_id,
                detail=e.detail,
                created_at=e.created_at,
            )
        )
    return out


@router.get("/backups")
def list_backups(
    limit: int = Query(default=50, ge=1, le=500),
    settings: Settings = Depends(get_settings_dep),
) -> list[BackupRunOut]:
    storage = build_storage(settings)
    # Keys are `_backups/<timestamp>.json`; the timestamp sorts lexicographically.
    keys = sorted(storage.list_prefix(BACKUP_PREFIX), reverse=True)[:limit]
    manifests = (_read_backup_manifest(storage, key) for key in keys)
    return [m for m in manifests if m is not None]


@router.get("/projects")
def list_projects(session: Session = Depends(session_dep)) -> list[AdminProjectOut]:
    """Projects with their run counts, for the admin management table."""
    counts: dict[str, int] = dict(
        session.execute(
            select(TestRun.project_id, func.count(TestRun.id)).group_by(TestRun.project_id)
        )
        .tuples()
        .all()
    )
    return [
        AdminProjectOut(id=p.id, slug=p.slug, name=p.name, run_count=counts.get(p.id, 0))
        for p in session.execute(select(Project).order_by(Project.slug)).scalars()
    ]


@router.delete("/projects/{slug}")
def delete_project_endpoint(
    slug: str,
    user: User = Depends(require_admin),
    session: Session = Depends(session_dep),
    settings: Settings = Depends(get_settings_dep),
) -> ProjectDeletedOut:
    """Permanently delete a project and every run/artifact/spec/view under it."""
    project = ProjectRepo(session).get_by_slug(slug)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    project_id = project.id
    # Record the deletion before the project row goes away; audit.project_id is a
    # plain (non-FK) column so the event survives as history.
    AuditRepo(session).record(
        user_id=user.id,
        action="project.delete",
        project_id=project_id,
        target_type="project",
        target_id=project_id,
        detail={"slug": slug, "name": project.name},
    )
    stats = delete_project(session, build_storage(settings), project_id=project_id)
    return ProjectDeletedOut(slug=slug, **stats)


@router.get("/logs")
def container_logs(
    service: str = Query(default="api"),
    tail: int = Query(default=200, ge=1, le=2000),
    settings: Settings = Depends(get_settings_dep),
) -> ContainerLogsOut:
    return read_container_logs(service, tail=tail, socket_path=settings.docker_socket)
