"""Command-line entry points for ops tasks."""

import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from prism_api.bootstrap import ensure_bootstrap_admin
from prism_api.config import Settings, get_settings
from prism_api.models.artifact import Artifact, ArtifactKind
from prism_api.models.suite import TestCase, TestSuite
from prism_api.parsers.logs import parse_log
from prism_api.repos.logs import LogRepo
from prism_api.storage import ObjectStorage, build_storage


def _resolve_run_id(session: Session, artifact: Artifact) -> str | None:
    """Return the TestRun id that owns *artifact*, following case/suite indirection."""
    if artifact.owner_type == "run":
        return artifact.owner_id
    if artifact.owner_type == "suite":
        suite = session.get(TestSuite, artifact.owner_id)
        return suite.run_id if suite is not None else None
    if artifact.owner_type == "case":
        case = session.get(TestCase, artifact.owner_id)
        if case is None:
            return None
        suite = session.get(TestSuite, case.suite_id)
        return suite.run_id if suite is not None else None
    return None


def bootstrap_admin(settings: Settings | None = None) -> None:
    """Create the bootstrap admin if no users exist and credentials are set."""
    s = settings or get_settings()
    engine = create_engine(s.database_url)
    try:
        with sessionmaker(bind=engine)() as session:
            ensure_bootstrap_admin(session, email=s.admin_email, password=s.admin_password)
            session.commit()
    finally:
        engine.dispose()


def ensure_bucket(settings: Settings | None = None) -> None:
    """Ensure the configured S3 bucket exists."""
    s = settings or get_settings()
    storage = build_storage(s)
    storage.ensure_bucket()


def reparse_logs(
    *,
    session: Session,
    storage: ObjectStorage,
    kernel_pattern: str,
    hdl_pattern: str,
    findings_cap: int,
) -> int:
    """(Re)build log_reports for every LOG_TEXT artifact that has none. Returns count."""
    repo = LogRepo(session)
    arts = session.execute(select(Artifact).where(Artifact.kind == ArtifactKind.LOG_TEXT)).scalars()
    count = 0
    for a in arts:
        run_id = _resolve_run_id(session, a)
        if run_id is None:
            continue
        if any(r.artifact_id == a.id for r in repo.list_by_run(run_id)):
            continue
        data = storage.get_bytes(a.storage_key)
        parsed = parse_log(
            data,
            kernel_pattern=kernel_pattern,
            hdl_pattern=hdl_pattern,
            findings_cap=findings_cap,
        )
        repo.create_report(run_id=run_id, artifact_id=a.id, source=a.filename, parsed=parsed)
        count += 1
    return count


def reparse_logs_cli(settings: Settings | None = None) -> None:
    """CLI wrapper: reparse all LOG_TEXT artifacts and persist reports."""
    s = settings or get_settings()
    engine = create_engine(s.database_url)
    storage = build_storage(s)
    try:
        with sessionmaker(bind=engine)() as session:
            n = reparse_logs(
                session=session,
                storage=storage,
                kernel_pattern=s.log_kernel_commit_pattern,
                hdl_pattern=s.log_hdl_commit_pattern,
                findings_cap=s.log_findings_cap,
            )
            session.commit()
    finally:
        engine.dispose()
    print(f"reparsed {n} log artifact(s)")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: prism-api <bootstrap-admin|ensure-bucket|reparse-logs>", file=sys.stderr)
        return 2
    cmd = sys.argv[1]
    if cmd == "bootstrap-admin":
        bootstrap_admin()
        return 0
    if cmd == "ensure-bucket":
        ensure_bucket()
        return 0
    if cmd == "reparse-logs":
        reparse_logs_cli()
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
