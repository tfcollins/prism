"""Compare runs."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from prism_api.deps import csrf_protect, current_user, session_dep
from prism_api.models.user import User
from prism_api.repos.runs import RunRepo
from prism_api.repos.suites import CaseRepo, SuiteRepo
from prism_api.schemas.compare import CaseDiff, CompareRequest, CompareResponse, RunHeader

router = APIRouter(prefix="/api/v1/compare", tags=["compare"])


@router.post("", response_model=CompareResponse)
def compare_runs(
    body: CompareRequest,
    _: User = Depends(current_user),
    __: None = Depends(csrf_protect),
    session: Session = Depends(session_dep),
) -> CompareResponse:
    runs_repo = RunRepo(session)
    suites_repo = SuiteRepo(session)
    cases_repo = CaseRepo(session)

    runs = []
    for run_id in body.run_ids:
        run = runs_repo.get_by_id(run_id)
        if run is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"run {run_id} not found")
        counts = runs_repo.aggregate_counts_by_run(run.id)
        runs.append(
            RunHeader(
                id=run.id, name=run.name, status=run.status.value,
                pass_count=counts["pass_count"], fail_count=counts["fail_count"],
            )
        )

    # Build per-run case-status map: {(suite_name, case_name): status}
    per_run_status: list[dict[tuple[str, str], str]] = []
    all_keys: set[tuple[str, str]] = set()
    for run_id in body.run_ids:
        m: dict[tuple[str, str], str] = {}
        for suite in suites_repo.list_by_run(run_id):
            for case in cases_repo.list_by_suite(suite.id):
                key = (suite.name, case.name)
                m[key] = case.status.value
                all_keys.add(key)
        per_run_status.append(m)

    cases = sorted(
        [
            CaseDiff(
                suite_name=key[0], classname="", name=key[1],
                statuses=[m.get(key) for m in per_run_status],
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

    return CompareResponse(runs=runs, cases=cases, pass_rate_delta=pr_delta)
