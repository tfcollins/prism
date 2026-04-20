"""Run upload endpoint."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from prism_api.config import Settings
from prism_api.deps import current_user, get_settings_dep, session_dep
from prism_api.models.run import RunStatus
from prism_api.models.user import User
from prism_api.repos.projects import ProjectRepo
from prism_api.repos.runs import RunRepo
from prism_api.schemas.run import CreateRunMetadata, RunOut, RunTagOut
from prism_api.storage import build_storage
from prism_api.worker.tasks import run_ingest

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


def enqueue_ingest(run_id: str, junit_xml: bytes, archive: bytes | None) -> None:
    """Thin seam so tests can replace the Celery dispatch with an inline call."""
    # Writing upload bodies to storage happens here so the worker can fetch by key.
    # For simplicity in v1 we pass bytes directly via a signed-URL or via a
    # call-site-provided storage. The task signature accepts byte payloads for test
    # friendliness; in production, consider uploading to S3 first and passing keys.
    run_ingest.delay(run_id, junit_xml, archive)  # type: ignore[arg-type]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=RunOut)
async def upload_run(
    junit: UploadFile = File(...),
    metadata: str = Form(...),
    archive: UploadFile | None = File(default=None),
    current: User = Depends(current_user),
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
    enqueue_ingest(run.id, junit_bytes, archive_bytes)

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
