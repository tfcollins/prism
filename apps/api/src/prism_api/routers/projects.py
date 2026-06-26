"""Project endpoints."""

import csv
import io
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from prism_api.deps import csrf_protect, current_user, require_admin, session_dep
from prism_api.models.user import User
from prism_api.repos.audit import AuditRepo
from prism_api.repos.export import EXPORT_COLUMNS, ExportRepo
from prism_api.repos.logs import LogRepo
from prism_api.repos.masks import MaskRepo
from prism_api.repos.projects import ProjectRepo
from prism_api.repos.runs import RunRepo
from prism_api.repos.specs import SpecRepo
from prism_api.repos.suites import MeasurementRepo
from prism_api.repos.tests_history import TestHistoryRepo
from prism_api.repos.views import ViewRepo
from prism_api.schemas.audit import AuditEventOut
from prism_api.schemas.case import measurement_margin
from prism_api.schemas.log import CommitCount
from prism_api.schemas.mask import MaskCreate, MaskOut, MaskSegment
from prism_api.schemas.project import CreateProjectRequest, ProjectOut, UpdateProjectRequest
from prism_api.schemas.spec import SpecDefinitionOut, SpecUpsert, resolve_spec
from prism_api.schemas.test_history import TestSummary, TestTimelinePoint
from prism_api.schemas.trend import (
    RegressionEvent,
    RegressionsResponse,
    TrendPoint,
    TrendResponse,
)
from prism_api.schemas.view import SavedViewOut, SavedViewUpsert

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _project_out(p: object) -> ProjectOut:
    return ProjectOut(
        id=p.id,  # type: ignore[attr-defined]
        slug=p.slug,  # type: ignore[attr-defined]
        name=p.name,  # type: ignore[attr-defined]
        description=p.description,  # type: ignore[attr-defined]
        genalyzer_auto=p.genalyzer_auto,  # type: ignore[attr-defined]
    )


@router.get("")
def list_projects(
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[ProjectOut]:
    return [_project_out(p) for p in ProjectRepo(session).list_all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(
    body: CreateProjectRequest,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> ProjectOut:
    try:
        p = ProjectRepo(session).create(
            slug=body.slug, name=body.name, description=body.description
        )
        session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "slug already exists") from exc
    return _project_out(p)


@router.get("/{slug}")
def get_project(
    slug: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> ProjectOut:
    p = ProjectRepo(session).get_by_slug(slug)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    return _project_out(p)


@router.patch("/{slug}", dependencies=[Depends(csrf_protect), Depends(require_admin)])
def update_project(
    slug: str,
    body: UpdateProjectRequest,
    session: Session = Depends(session_dep),
) -> ProjectOut:
    p = ProjectRepo(session).get_by_slug(slug)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    p.genalyzer_auto = body.genalyzer_auto
    session.flush()
    return _project_out(p)


@router.get("/{slug}/measurements")
def list_measurement_names(
    slug: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[str]:
    p = ProjectRepo(session).get_by_slug(slug)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    return MeasurementRepo(session).distinct_names_for_project(p.id)


@router.get("/{slug}/measurements/{name}/trend", response_model=TrendResponse)
def measurement_trend(
    slug: str,
    name: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> TrendResponse:
    p = ProjectRepo(session).get_by_slug(slug)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    runs_repo = RunRepo(session)
    proj_spec = SpecRepo(session).get(p.id, name)
    pmin = proj_spec.spec_min if proj_spec else None
    pmax = proj_spec.spec_max if proj_spec else None
    points: list[TrendPoint] = []
    for m, case, run in MeasurementRepo(session).trend_for_project(p.id, name):
        smin, smax = resolve_spec(m.spec_min, m.spec_max, pmin, pmax)
        margin = measurement_margin(m.value, smin, smax)
        points.append(
            TrendPoint(
                run_id=run.id,
                run_name=run.name,
                created_at=run.created_at,
                case_id=case.id,
                case_name=case.name,
                value=m.value,
                unit=m.unit,
                spec_min=smin,
                spec_max=smax,
                in_spec=None if margin is None else margin >= 0,
                margin=margin,
                tags={t.key: t.value for t in runs_repo.tags_for(run.id)},
            )
        )
    return TrendResponse(measurement_name=name, points=points)


@router.get("/{slug}/regressions", response_model=RegressionsResponse)
def measurement_regressions(
    slug: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> RegressionsResponse:
    """Spec-crossing events across the project: a measurement that is out of
    spec, flagged ``crossed_out`` the run it first went out (its previous run
    was in spec) and ``still_out`` while it stays out."""
    p = _project_or_404(session, slug)
    meas_repo = MeasurementRepo(session)
    spec_map = SpecRepo(session).map_for_project(p.id)
    events: list[RegressionEvent] = []
    for name in meas_repo.distinct_names_for_project(p.id):
        ps = spec_map.get(name)
        pmin = ps.spec_min if ps else None
        pmax = ps.spec_max if ps else None
        prev_in_spec: bool | None = None
        prev_value: float | None = None
        for m, _case, run in meas_repo.trend_for_project(p.id, name):
            smin, smax = resolve_spec(m.spec_min, m.spec_max, pmin, pmax)
            margin = measurement_margin(m.value, smin, smax)
            in_spec = None if margin is None else margin >= 0
            if in_spec is False:
                events.append(
                    RegressionEvent(
                        measurement_name=name,
                        run_id=run.id,
                        run_name=run.name,
                        created_at=run.created_at,
                        value=m.value,
                        unit=m.unit,
                        previous_value=prev_value,
                        kind="crossed_out" if prev_in_spec else "still_out",
                    )
                )
            prev_in_spec = in_spec
            prev_value = m.value
    events.sort(key=lambda e: e.created_at, reverse=True)
    return RegressionsResponse(events=events)


@router.get("/{slug}/tests")
def list_tests(
    slug: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[TestSummary]:
    """Per-test aggregates across the project's runs, sorted flakiest-first."""
    p = _project_or_404(session, slug)
    return [TestSummary.model_validate(r) for r in TestHistoryRepo(session).aggregate(p.id)]


@router.get("/{slug}/tests/history")
def test_history(
    slug: str,
    classname: str = Query(...),
    name: str = Query(...),
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[TestTimelinePoint]:
    """Per-run timeline (status + duration) for one test, oldest first."""
    p = _project_or_404(session, slug)
    rows = TestHistoryRepo(session).timeline(p.id, classname, name)
    return [TestTimelinePoint.model_validate(r) for r in rows]


@router.get("/{slug}/export.csv")
def export_csv(
    slug: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> StreamingResponse:
    """Stream every case (+ measurements) in the project as CSV."""
    p = _project_or_404(session, slug)
    rows = ExportRepo(session).rows(p.id)

    def generate() -> Iterator[str]:
        buf = io.StringIO()
        writer = csv.writer(buf)

        def flush() -> str:
            out = buf.getvalue()
            buf.seek(0)
            buf.truncate(0)
            return out

        writer.writerow(EXPORT_COLUMNS)
        yield flush()
        for r in rows:
            writer.writerow(["" if v is None else v for v in r])
            yield flush()

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{slug}-export.csv"'},
    )


def _project_or_404(session: Session, slug: str):  # type: ignore[no-untyped-def]
    p = ProjectRepo(session).get_by_slug(slug)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    return p


def _mask_out(mask: Any) -> MaskOut:
    return MaskOut(
        id=mask.id,
        project_id=mask.project_id,
        name=mask.name,
        segments=[MaskSegment(**s) for s in mask.segments],
    )


@router.get("/{slug}/masks")
def list_masks(
    slug: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[MaskOut]:
    p = _project_or_404(session, slug)
    return [_mask_out(m) for m in MaskRepo(session).list_by_project(p.id)]


@router.post("/{slug}/masks", status_code=status.HTTP_201_CREATED)
def create_mask(
    slug: str,
    body: MaskCreate,
    user: User = Depends(current_user),
    __: None = Depends(csrf_protect),
    session: Session = Depends(session_dep),
) -> MaskOut:
    p = _project_or_404(session, slug)
    mask = MaskRepo(session).create(
        project_id=p.id,
        name=body.name,
        segments=[s.model_dump() for s in body.segments],
    )
    AuditRepo(session).record(
        user_id=user.id,
        action="mask.create",
        project_id=p.id,
        target_type="mask",
        target_id=mask.id,
        detail={"name": body.name},
    )
    session.commit()
    return _mask_out(mask)


@router.delete("/{slug}/masks/{mask_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mask(
    slug: str,
    mask_id: str,
    user: User = Depends(current_user),
    __: None = Depends(csrf_protect),
    session: Session = Depends(session_dep),
) -> None:
    p = _project_or_404(session, slug)
    repo = MaskRepo(session)
    if repo.get(mask_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "mask not found")
    repo.delete(mask_id)
    AuditRepo(session).record(
        user_id=user.id,
        action="mask.delete",
        project_id=p.id,
        target_type="mask",
        target_id=mask_id,
    )
    session.commit()


@router.get("/{slug}/audit")
def list_audit(
    slug: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[AuditEventOut]:
    p = _project_or_404(session, slug)
    events = AuditRepo(session).list_for_project(p.id)
    email_cache: dict[str, str | None] = {}
    out: list[AuditEventOut] = []
    for e in events:
        email: str | None = None
        if e.user_id is not None:
            if e.user_id not in email_cache:
                u = session.get(User, e.user_id)
                email_cache[e.user_id] = u.email if u else None
            email = email_cache[e.user_id]
        out.append(
            AuditEventOut(
                action=e.action,
                user_email=email,
                target_type=e.target_type,
                target_id=e.target_id,
                detail=e.detail,
                created_at=e.created_at,
            )
        )
    return out


def _spec_out(s: Any) -> SpecDefinitionOut:
    return SpecDefinitionOut(
        measurement_name=s.measurement_name,
        spec_min=s.spec_min,
        spec_max=s.spec_max,
        unit=s.unit,
    )


@router.get("/{slug}/specs")
def list_specs(
    slug: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[SpecDefinitionOut]:
    p = _project_or_404(session, slug)
    return [_spec_out(s) for s in SpecRepo(session).list_by_project(p.id)]


@router.put("/{slug}/specs")
def upsert_spec(
    slug: str,
    body: SpecUpsert,
    user: User = Depends(current_user),
    __: None = Depends(csrf_protect),
    session: Session = Depends(session_dep),
) -> SpecDefinitionOut:
    p = _project_or_404(session, slug)
    spec = SpecRepo(session).upsert(
        project_id=p.id,
        measurement_name=body.measurement_name,
        spec_min=body.spec_min,
        spec_max=body.spec_max,
        unit=body.unit,
    )
    AuditRepo(session).record(
        user_id=user.id,
        action="spec.upsert",
        project_id=p.id,
        target_type="spec",
        target_id=body.measurement_name,
        detail={"spec_min": body.spec_min, "spec_max": body.spec_max},
    )
    session.commit()
    return _spec_out(spec)


@router.delete("/{slug}/specs/{measurement_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_spec(
    slug: str,
    measurement_name: str,
    user: User = Depends(current_user),
    __: None = Depends(csrf_protect),
    session: Session = Depends(session_dep),
) -> None:
    p = _project_or_404(session, slug)
    if not SpecRepo(session).delete(p.id, measurement_name):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "spec not found")
    AuditRepo(session).record(
        user_id=user.id,
        action="spec.delete",
        project_id=p.id,
        target_type="spec",
        target_id=measurement_name,
    )
    session.commit()


@router.get("/{slug}/tag-keys")
def list_tag_keys(
    slug: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[str]:
    p = _project_or_404(session, slug)
    return RunRepo(session).distinct_tag_keys(p.id)


@router.get("/{slug}/tag-values")
def list_tag_values(
    slug: str,
    key: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[dict[str, Any]]:
    p = _project_or_404(session, slug)
    return [{"value": v, "run_count": c} for v, c in RunRepo(session).tag_value_counts(p.id, key)]


@router.get("/{slug}/commits")
def list_commits(
    slug: str,
    type: str = "kernel",
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[CommitCount]:
    p = _project_or_404(session, slug)
    if type not in ("kernel", "hdl"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "type must be kernel or hdl")
    return [
        CommitCount(commit=c, run_count=n)
        for c, n in LogRepo(session).commit_counts_for_project(type, p.id)
    ]


@router.get("/{slug}/views")
def list_views(
    slug: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[SavedViewOut]:
    p = _project_or_404(session, slug)
    return [
        SavedViewOut(name=v.name, config=v.config) for v in ViewRepo(session).list_by_project(p.id)
    ]


@router.put("/{slug}/views")
def upsert_view(
    slug: str,
    body: SavedViewUpsert,
    user: User = Depends(current_user),
    __: None = Depends(csrf_protect),
    session: Session = Depends(session_dep),
) -> SavedViewOut:
    p = _project_or_404(session, slug)
    v = ViewRepo(session).upsert(project_id=p.id, name=body.name, config=body.config)
    AuditRepo(session).record(
        user_id=user.id,
        action="view.upsert",
        project_id=p.id,
        target_type="view",
        target_id=body.name,
    )
    session.commit()
    return SavedViewOut(name=v.name, config=v.config)


@router.delete("/{slug}/views/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_view(
    slug: str,
    name: str,
    _: User = Depends(current_user),
    __: None = Depends(csrf_protect),
    session: Session = Depends(session_dep),
) -> None:
    p = _project_or_404(session, slug)
    if not ViewRepo(session).delete(p.id, name):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "view not found")
    session.commit()
