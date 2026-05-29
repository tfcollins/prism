"""Landing/overview endpoint: database-wide stats, recent runs, daily activity."""

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from prism_api.deps import current_user, session_dep
from prism_api.models.user import User
from prism_api.repos.runs import RunRepo
from prism_api.repos.stats import StatsRepo
from prism_api.schemas.overview import DailyPoint, OverviewResponse, OverviewStats, RecentRun

router = APIRouter(prefix="/api/v1/overview", tags=["overview"])

_DAYS = 30


def _daily_series(rows: list[tuple[datetime, int]], days: int) -> list[DailyPoint]:
    today = datetime.now(UTC).date()
    start = today - timedelta(days=days - 1)
    runs_by: dict[str, int] = defaultdict(int)
    fails_by: dict[str, int] = defaultdict(int)
    for created_at, failures in rows:
        key = created_at.date().isoformat()
        runs_by[key] += 1
        fails_by[key] += failures
    out: list[DailyPoint] = []
    for i in range(days):
        d = (start + timedelta(days=i)).isoformat()
        out.append(DailyPoint(date=d, runs=runs_by.get(d, 0), failures=fails_by.get(d, 0)))
    return out


@router.get("")
def get_overview(
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> OverviewResponse:
    stats_repo = StatsRepo(session)
    runs_repo = RunRepo(session)

    t = stats_repo.totals()
    total_tests = t["passed"] + t["failed"] + t["errored"] + t["skipped"]
    total_failures = t["failed"] + t["errored"]
    stats = OverviewStats(
        total_projects=t["total_projects"],
        total_runs=t["total_runs"],
        total_tests=total_tests,
        total_failures=total_failures,
        pass_rate=(t["passed"] / total_tests) if total_tests else 0.0,
    )

    recent: list[RecentRun] = []
    for run, slug, name in stats_repo.recent_runs(limit=10):
        counts = runs_repo.aggregate_counts_by_run(run.id)
        recent.append(
            RecentRun(
                id=run.id,
                name=run.name,
                project_slug=slug,
                project_name=name,
                status=str(run.status),
                created_at=run.created_at,
                pass_count=counts["pass_count"],
                fail_count=counts["fail_count"] + counts["error_count"],
            )
        )

    daily = _daily_series(stats_repo.daily_run_failures(days=_DAYS), _DAYS)
    return OverviewResponse(stats=stats, recent_runs=recent, daily=daily)
