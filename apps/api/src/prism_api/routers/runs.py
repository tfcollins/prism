"""Run upload + read endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from prism_api.config import Settings
from prism_api.deps import csrf_protect, current_user, get_settings_dep, session_dep
from prism_api.models.run import RunStatus
from prism_api.models.user import User
from prism_api.reports.run_report import ReportMeasurement, RunReport, build_run_report_pdf
from prism_api.repos.artifacts import ArtifactRepo
from prism_api.repos.audit import AuditRepo
from prism_api.repos.logs import LogRepo
from prism_api.repos.projects import ProjectRepo
from prism_api.repos.runs import RunRepo
from prism_api.repos.specs import SpecRepo
from prism_api.repos.suites import MeasurementRepo, SuiteRepo
from prism_api.schemas.artifact import ArtifactOut
from prism_api.schemas.case import measurement_margin
from prism_api.schemas.log import FindingOut, LogReportOut, commit_url
from prism_api.schemas.run import (
    CreateRunMetadata,
    RunDetail,
    RunListItem,
    RunOut,
    RunTagOut,
    SetCalibrationRequest,
    SuiteSummary,
)
from prism_api.schemas.spec import resolve_spec
from prism_api.services.boot_summary import build_boot_summary
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
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"invalid metadata: {exc}"
        ) from exc

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
    AuditRepo(session).record(
        user_id=current.id,
        action="run.upload",
        project_id=project.id,
        target_type="run",
        target_id=run.id,
        detail={"name": meta.name},
    )
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
    tag_key: str | None = Query(default=None),
    tag_value: str | None = Query(default=None),
    kernel_commit: str | None = Query(default=None),
    hdl_commit: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[RunListItem]:
    proj = ProjectRepo(session).get_by_slug(project)
    if proj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"project '{project}' not found")
    runs = RunRepo(session)
    suites_repo = SuiteRepo(session)
    items = runs.list_with_filters(
        project_id=proj.id,
        status=status_,
        tag_key=tag_key,
        tag_value=tag_value,
        kernel_commit=kernel_commit,
        hdl_commit=hdl_commit,
        limit=limit,
    )
    result: list[RunListItem] = []
    for r in items:
        counts = runs.aggregate_counts_by_run(r.id)
        tags = runs.tags_for(r.id)
        suites = suites_repo.list_by_run(r.id)
        result.append(
            RunListItem(
                id=r.id,
                project_id=r.project_id,
                name=r.name,
                status=r.status.value,
                started_at=r.started_at,
                finished_at=r.finished_at,
                created_at=r.created_at,
                suite_names=[s.name for s in suites],
                tags=[RunTagOut(key=t.key, value=t.value) for t in tags],
                **counts,
            )
        )
    return result


@router.get("/{run_id}", response_model=RunDetail)
def get_run(
    run_id: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
    settings: Settings = Depends(get_settings_dep),
) -> RunDetail:
    runs = RunRepo(session)
    run = runs.get_by_id(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    suites = [
        SuiteSummary(
            id=s.id,
            name=s.name,
            pass_count=s.pass_count,
            fail_count=s.fail_count,
            error_count=s.error_count,
            skip_count=s.skip_count,
            duration_ms=s.duration_ms,
        )
        for s in SuiteRepo(session).list_by_run(run.id)
    ]
    tags = [RunTagOut(key=t.key, value=t.value) for t in runs.tags_for(run.id)]
    project = ProjectRepo(session).get_by_id(run.project_id)
    cal = runs.get_by_id(run.calibration_run_id) if run.calibration_run_id else None
    boot = build_boot_summary(LogRepo(session), run.id, settings, run.project_id)
    return RunDetail(
        id=run.id,
        project_id=run.project_id,
        project_slug=project.slug if project else None,
        name=run.name,
        status=run.status.value,
        started_at=run.started_at,
        finished_at=run.finished_at,
        junit_artifact_id=run.junit_artifact_id,
        calibration_run_id=run.calibration_run_id,
        calibration_run_name=cal.name if cal else None,
        tags=tags,
        suites=suites,
        boot=boot,
    )


@router.get("/{run_id}/logs", response_model=list[LogReportOut])
def get_run_logs(
    run_id: str,
    _: User = Depends(current_user),
    settings: Settings = Depends(get_settings_dep),
    session: Session = Depends(session_dep),
) -> list[LogReportOut]:
    runs = RunRepo(session)
    if runs.get_by_id(run_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    repo = LogRepo(session)
    out: list[LogReportOut] = []
    for r in repo.list_by_run(run_id):
        out.append(
            LogReportOut(
                source=r.source,
                kernel_version=r.kernel_version,
                board=r.board,
                kernel_commit=r.kernel_commit,
                hdl_commit=r.hdl_commit,
                kernel_commit_url=commit_url(settings.kernel_repo_url, r.kernel_commit),
                hdl_commit_url=commit_url(settings.hdl_repo_url, r.hdl_commit),
                error_count=r.error_count,
                warn_count=r.warn_count,
                has_panic=r.has_panic,
                findings=[
                    FindingOut(severity=f.severity, line_no=f.line_no, text=f.text)
                    for f in repo.findings_for(r.id)
                ],
            )
        )
    return out


@router.patch("/{run_id}/calibration", response_model=RunDetail)
def set_calibration(
    run_id: str,
    body: SetCalibrationRequest,
    user: User = Depends(current_user),
    __: None = Depends(csrf_protect),
    session: Session = Depends(session_dep),
    settings: Settings = Depends(get_settings_dep),
) -> RunDetail:
    runs = RunRepo(session)
    run = runs.get_by_id(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    cal_id = body.calibration_run_id
    if cal_id is not None:
        if cal_id == run_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "a run cannot calibrate itself")
        cal = runs.get_by_id(cal_id)
        if cal is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "calibration run not found")
        if cal.project_id != run.project_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "calibration run must be in the same project"
            )
    runs.set_calibration_run(run_id, cal_id)
    AuditRepo(session).record(
        user_id=user.id,
        action="run.set_calibration",
        project_id=run.project_id,
        target_type="run",
        target_id=run_id,
        detail={"calibration_run_id": cal_id},
    )
    session.commit()
    return get_run(run_id, user, session, settings)


@router.get("/{run_id}/artifacts", response_model=list[ArtifactOut])
def list_run_artifacts(
    run_id: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[ArtifactOut]:
    """Return all run-scoped artifacts (boot.log, dmesg_*, iio_info.txt, etc.).

    Per-case artifacts are reachable via /api/v1/cases/{id}; this endpoint
    is the parallel for run-scoped owners.
    """
    runs = RunRepo(session)
    if runs.get_by_id(run_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    arts = ArtifactRepo(session).list_by_owner("run", run_id)
    return [
        ArtifactOut(
            id=a.id,
            owner_type=a.owner_type,
            owner_id=a.owner_id,
            kind=a.kind.value,
            filename=a.filename,
            size_bytes=a.size_bytes,
            content_hash=a.content_hash,
        )
        for a in arts
    ]


@router.get("/{run_id}/report.pdf")
def run_report(
    run_id: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> Response:
    runs = RunRepo(session)
    run = runs.get_by_id(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    project = ProjectRepo(session).get_by_id(run.project_id)
    counts = runs.aggregate_counts_by_run(run.id)
    tags = {t.key: t.value for t in runs.tags_for(run.id)}

    spec_map = SpecRepo(session).map_for_project(run.project_id)
    measurements: list[ReportMeasurement] = []
    for m in MeasurementRepo(session).list_by_run(run.id):
        ps = spec_map.get(m.name)
        smin, smax = resolve_spec(
            m.spec_min, m.spec_max, ps.spec_min if ps else None, ps.spec_max if ps else None
        )
        margin = measurement_margin(m.value, smin, smax)
        measurements.append(
            ReportMeasurement(
                name=m.name,
                value=m.value,
                unit=m.unit,
                spec_min=smin,
                spec_max=smax,
                in_spec=None if margin is None else margin >= 0,
                margin=margin,
            )
        )

    junit_sha: str | None = None
    if run.junit_artifact_id:
        art = ArtifactRepo(session).get_by_id(run.junit_artifact_id)
        junit_sha = art.content_hash if art else None

    pdf_bytes = build_run_report_pdf(
        RunReport(
            run_name=run.name,
            project_name=project.name if project else run.project_id,
            status=run.status.value,
            tags=tags,
            pass_count=counts["pass_count"],
            fail_count=counts["fail_count"],
            measurements=measurements,
            junit_sha=junit_sha,
        )
    )
    filename = f"{run.name}-report.pdf".replace("/", "_").replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
