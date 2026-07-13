"""Resolve a run's boot summary from its (possibly several) log reports."""

from prism_api.config import Settings
from prism_api.repos.logs import LogRepo
from prism_api.schemas.log import BootSummary, commit_url


def build_boot_summary(
    repo: LogRepo, run_id: str, settings: Settings, project_id: str | None = None
) -> BootSummary | None:
    reports = repo.list_by_run(run_id)
    # Exclude terminal/console/stdout/stderr logs from boot summary
    reports = [
        r for r in reports
        if not any(k in r.source.lower() for k in ("terminal", "console", "stdout", "stderr"))
    ]
    if not reports:
        return None


    def first(attr: str) -> str | None:
        for r in reports:  # oldest-first (list_by_run orders by created_at)
            v: str | None = getattr(r, attr)
            if v:
                return v
        return None

    kernel_commit = first("kernel_commit")
    hdl_commit = first("hdl_commit")
    return BootSummary(
        kernel_version=first("kernel_version"),
        board=first("board"),
        kernel_commit=kernel_commit,
        hdl_commit=hdl_commit,
        kernel_commit_url=commit_url(settings.kernel_repo_url, kernel_commit),
        hdl_commit_url=commit_url(settings.hdl_repo_url, hdl_commit),
        error_count=sum(r.error_count for r in reports),
        warn_count=sum(r.warn_count for r in reports),
        has_panic=any(r.has_panic for r in reports),
        shared_kernel_count=(
            repo.shared_count("kernel", kernel_commit, exclude_run_id=run_id, project_id=project_id)
            if kernel_commit
            else 0
        ),
        shared_hdl_count=(
            repo.shared_count("hdl", hdl_commit, exclude_run_id=run_id, project_id=project_id)
            if hdl_commit
            else 0
        ),
    )
