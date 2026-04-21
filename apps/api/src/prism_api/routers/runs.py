"""Run upload + read endpoints."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from prism_api.config import Settings
from prism_api.deps import csrf_protect, current_user, get_settings_dep, session_dep
from prism_api.models.run import RunStatus
from prism_api.models.user import User
from prism_api.repos.projects import ProjectRepo
from prism_api.repos.runs import RunRepo
from prism_api.repos.suites import SuiteRepo
from prism_api.schemas.run import (
    CreateRunMetadata,
    RunDetail,
    RunListItem,
    RunOut,
    RunTagOut,
    SuiteSummary,
)
from prism_api.storage import ObjectStorage, build_storage
from prism_api.worker.tasks import run_ingest

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


def enqueue_ingest(
    run_id: str,
    junit_bytes: bytes,
    archive_bytes: bytes | None,
    storage: ObjectStorage,
) -> None:
    """Upload payloads to S3 then dispatch the Celery task with keys (JSON-serializer safe)."""
    junit_key = storage.put_raw(junit_bytes, filename="junit.xml")
    archive_key = storage.put_raw(archive_bytes, filename="archive.zip") if archive_bytes else None
    run_ingest.delay(run_id, junit_key, archive_key)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=RunOut)
async def upload_run(
    junit: UploadFile = File(...),
    metadata: str = Form(...),
    archive: UploadFile | None = File(default=None),
    current: User = Depends(current_user),
    _csrf: None = Depends(csrf_protect),
    settings: Settings = Depends(get_settings_dep),
    session: Session = Depends(session_dep),
) -> RunOut:
    # 1) Parse metadata JSON
    try:
        meta = CreateRunMetadata.model_validate(json.loads(metadata))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"invalid metadata: {exc}") from exc

    # 2) Resolve project
    project = ProjectRepo(session).get_by_slug(meta.project_slug)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"project '{meta.project_slug}' not found")

    # 3) Create run row
    runs = RunRepo(session)
    run = runs.create(
        project_id=project.id,
        name=meta.name,
        status=RunStatus.PENDING,
        created_by=current.id,
    )
    for k, v in meta.tags.items():
        runs.add_tag(run.id, k, v)
    session.flush()

    # 4) Read payloads
    junit_bytes = await junit.read()
    archive_bytes = await archive.read() if archive is not None else None

    # 5) Run ingest (inline seam for tests; in prod dispatches to Celery worker)
    storage = build_storage(settings)
    storage.ensure_bucket()
    enqueue_ingest(run.id, junit_bytes, archive_bytes, storage)

    # 6) Respond with the current run state (status may be set by synchronous ingest in tests)
    session.refresh(run)
    tags = runs.tags_for(run.id)
    return RunOut(
        id=run.id,
        project_id=run.project_id,
        name=run.name,
        status=run.status.value,
        started_at=run.started_at,
        finished_at=run.finished_at,
        junit_artifact_id=run.junit_artifact_id,
        tags=[RunTagOut(key=t.key, value=t.value) for t in tags],
    )


@router.get("", response_model=list[RunListItem])
def list_runs(
    project: str = Query(..., description="Project slug"),
    status_: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[RunListItem]:
    proj = ProjectRepo(session).get_by_slug(project)
    if proj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"project '{project}' not found")
    runs = RunRepo(session)
    suites_repo = SuiteRepo(session)
    items = runs.list_with_filters(project_id=proj.id, status=status_, limit=limit)
    result: list[RunListItem] = []
    for r in items:
        counts = runs.aggregate_counts_by_run(r.id)
        tags = runs.tags_for(r.id)
        suites = suites_repo.list_by_run(r.id)
        result.append(RunListItem(
            id=r.id, project_id=r.project_id, name=r.name, status=r.status.value,
            started_at=r.started_at, finished_at=r.finished_at,
            created_at=r.created_at,
            suite_names=[s.name for s in suites],
            tags=[RunTagOut(key=t.key, value=t.value) for t in tags],
            **counts,
        ))
    return result


@router.get("/{run_id}", response_model=RunDetail)
def get_run(
    run_id: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> RunDetail:
    runs = RunRepo(session)
    run = runs.get_by_id(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    suites = [
        SuiteSummary(
            id=s.id, name=s.name, pass_count=s.pass_count, fail_count=s.fail_count,
            error_count=s.error_count, skip_count=s.skip_count, duration_ms=s.duration_ms,
        )
        for s in SuiteRepo(session).list_by_run(run.id)
    ]
    tags = [RunTagOut(key=t.key, value=t.value) for t in runs.tags_for(run.id)]
    return RunDetail(
        id=run.id, project_id=run.project_id, name=run.name, status=run.status.value,
        started_at=run.started_at, finished_at=run.finished_at,
        junit_artifact_id=run.junit_artifact_id, tags=tags, suites=suites,
    )
