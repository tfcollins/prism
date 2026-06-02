"""Compare runs."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from prism_api.config import Settings
from prism_api.deps import csrf_protect, current_user, get_settings_dep, session_dep
from prism_api.models import ArtifactKind
from prism_api.models.user import User
from prism_api.reports.compare_report import build_compare_report_pdf
from prism_api.repos.artifacts import ArtifactRepo
from prism_api.repos.logs import LogRepo
from prism_api.repos.projects import ProjectRepo
from prism_api.repos.runs import RunRepo
from prism_api.repos.suites import CaseRepo, MeasurementRepo, SuiteRepo
from prism_api.schemas.compare import (
    CaseDiff,
    CompareRequest,
    CompareResponse,
    MeasurementDiff,
    RunHeader,
)
from prism_api.services.boot_summary import build_boot_summary

router = APIRouter(prefix="/api/v1/compare", tags=["compare"])

_WAVEFORM_KINDS = {
    ArtifactKind.WAVEFORM_CSV,
    ArtifactKind.WAVEFORM_NPY,
    ArtifactKind.WAVEFORM_HDF5,
}

_MAX_REPORT_RUNS = 20


@router.post("", response_model=CompareResponse)
def compare_runs(
    body: CompareRequest,
    _: User = Depends(current_user),
    __: None = Depends(csrf_protect),
    session: Session = Depends(session_dep),
    settings: Settings = Depends(get_settings_dep),
) -> CompareResponse:
    return assemble_comparison(session, body.run_ids, settings)


@router.get("/report.pdf")
def compare_report(
    runs: str = Query(..., description="Comma-separated run ids"),
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
    settings: Settings = Depends(get_settings_dep),
) -> Response:
    """Render a multi-run comparison as a downloadable landscape-A4 PDF."""
    run_ids = [r for r in runs.split(",") if r]
    if not run_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no run ids provided")
    if len(run_ids) > _MAX_REPORT_RUNS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"too many runs (max {_MAX_REPORT_RUNS})")

    data = assemble_comparison(session, run_ids, settings)  # 404s on unknown id

    runs_repo = RunRepo(session)
    project_repo = ProjectRepo(session)
    project_names: list[str] = []
    seen: set[str] = set()
    for rid in run_ids:
        run = runs_repo.get_by_id(rid)
        if run is None or run.project_id in seen:
            continue
        seen.add(run.project_id)
        proj = project_repo.get_by_id(run.project_id)
        project_names.append(proj.name if proj is not None else run.project_id)

    pdf_bytes = build_compare_report_pdf(
        data=data, project_names=project_names, generated_at=datetime.now(UTC)
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="comparison-report.pdf"'},
    )


def assemble_comparison(
    session: Session, run_ids: list[str], settings: Settings
) -> CompareResponse:
    """Assemble the cross-run comparison shared by the JSON and PDF endpoints."""
    runs_repo = RunRepo(session)
    suites_repo = SuiteRepo(session)
    cases_repo = CaseRepo(session)
    artifacts_repo = ArtifactRepo(session)

    runs = []
    run_project_ids: dict[str, str] = {}
    for run_id in run_ids:
        run = runs_repo.get_by_id(run_id)
        if run is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"run {run_id} not found")
        run_project_ids[run.id] = run.project_id
        counts = runs_repo.aggregate_counts_by_run(run.id)
        runs.append(
            RunHeader(
                id=run.id,
                name=run.name,
                status=run.status.value,
                pass_count=counts["pass_count"],
                fail_count=counts["fail_count"],
            )
        )

    # Build per-run case-status map and per-run case-id map for artifact lookup
    per_run_status: list[dict[tuple[str, str], str]] = []
    per_run_case_id: list[dict[tuple[str, str], str]] = []
    all_keys: set[tuple[str, str]] = set()
    for run_id in run_ids:
        status_map: dict[tuple[str, str], str] = {}
        case_id_map: dict[tuple[str, str], str] = {}
        for suite in suites_repo.list_by_run(run_id):
            for case in cases_repo.list_by_suite(suite.id):
                key = (suite.name, case.name)
                status_map[key] = case.status.value
                case_id_map[key] = case.id
                all_keys.add(key)
        per_run_status.append(status_map)
        per_run_case_id.append(case_id_map)

    def _first_waveform_id(case_id: str) -> str | None:
        for art in artifacts_repo.list_by_owner("case", case_id):
            if art.kind in _WAVEFORM_KINDS:
                return art.id
        return None

    cases = sorted(
        [
            CaseDiff(
                suite_name=key[0],
                classname="",
                name=key[1],
                statuses=[m.get(key) for m in per_run_status],
                waveform_artifact_ids=[
                    _first_waveform_id(case_id_map[key]) if key in case_id_map else None
                    for case_id_map in per_run_case_id
                ],
            )
            for key in all_keys
        ],
        key=lambda c: (c.suite_name, c.name),
    )

    # pass-rate delta: (last.pass / total) - (first.pass / total)
    pr_delta: float | None
    first_total = runs[0].pass_count + runs[0].fail_count
    last_total = runs[-1].pass_count + runs[-1].fail_count
    if first_total == 0 or last_total == 0:
        pr_delta = None
    else:
        pr_delta = (runs[-1].pass_count / last_total) - (runs[0].pass_count / first_total)

    measurement_diffs = _measurement_diffs(MeasurementRepo(session), run_ids)

    log_repo = LogRepo(session)
    boots = [
        build_boot_summary(log_repo, rid, settings, run_project_ids.get(rid)) for rid in run_ids
    ]

    return CompareResponse(
        runs=runs,
        cases=cases,
        pass_rate_delta=pr_delta,
        measurement_diffs=measurement_diffs,
        boots=boots,
    )


def _measurement_diffs(repo: MeasurementRepo, run_ids: list[str]) -> list[MeasurementDiff]:
    """Per-measurement values aligned across runs, with a first→last delta.

    When a measurement name occurs in more than one case within a run, the first
    occurrence (by name-sorted order) is used — compare is a run-level summary,
    not a per-case view.
    """
    # name -> {unit, per-run value}
    per_run: list[dict[str, float]] = []
    units: dict[str, str | None] = {}
    names: list[str] = []
    seen: set[str] = set()
    for run_id in run_ids:
        values: dict[str, float] = {}
        for m in repo.list_by_run(run_id):
            if m.name not in values:  # keep first occurrence
                values[m.name] = m.value
                units.setdefault(m.name, m.unit)
            if m.name not in seen:
                seen.add(m.name)
                names.append(m.name)
        per_run.append(values)

    diffs: list[MeasurementDiff] = []
    for name in sorted(names):
        row: list[float | None] = [run_values.get(name) for run_values in per_run]
        first, last = row[0], row[-1]
        delta = last - first if first is not None and last is not None else None
        diffs.append(MeasurementDiff(name=name, unit=units.get(name), values=row, delta=delta))
    return diffs
