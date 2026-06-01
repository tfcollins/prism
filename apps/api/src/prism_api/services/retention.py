"""Retention: prune old runs and their orphaned artifact blobs.

Foreign-key cascades aren't enforced on SQLite (tests), so rows are deleted
explicitly in FK-safe order. Artifact blobs are content-addressed (shared
``storage_key``), so a blob is deleted from object storage only when no
surviving Artifact/DerivedArtifact still references it.
"""

import contextlib
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from prism_api.models.artifact import Artifact, DerivedArtifact
from prism_api.models.log import LogFinding, LogReport
from prism_api.models.mask import SpectrumMask
from prism_api.models.project import Project
from prism_api.models.run import RunTag, TestRun
from prism_api.models.spec import SpecDefinition
from prism_api.models.suite import TestCase, TestSuite
from prism_api.models.view import SavedView
from prism_api.storage import ObjectStorage


def _orphan_keys(
    session: Session,
    keys: Iterable[str],
    *,
    exclude_artifact_ids: set[str] | None = None,
    exclude_derived_ids: set[str] | None = None,
) -> set[str]:
    """Keys whose only Artifact/DerivedArtifact references are in the excluded sets."""
    eai = exclude_artifact_ids or set()
    edi = exclude_derived_ids or set()
    orphan: set[str] = set()
    for key in keys:
        art_ids = (
            session.execute(select(Artifact.id).where(Artifact.storage_key == key)).scalars().all()
        )
        der_ids = (
            session.execute(select(DerivedArtifact.id).where(DerivedArtifact.storage_key == key))
            .scalars()
            .all()
        )
        if all(a in eai for a in art_ids) and all(d in edi for d in der_ids):
            orphan.add(key)
    return orphan


class _RunArtifacts:
    """Artifact/derived ids + their storage keys for a set of runs."""

    def __init__(
        self,
        suite_ids: list[str],
        case_ids: list[str],
        art_ids: set[str],
        der_ids: set[str],
        candidate_keys: set[str],
    ) -> None:
        self.suite_ids = suite_ids
        self.case_ids = case_ids
        self.art_ids = art_ids
        self.der_ids = der_ids
        self.candidate_keys = candidate_keys


def _collect_run_artifacts(session: Session, run_ids: list[str]) -> _RunArtifacts:
    """Gather every suite/case/artifact/derived id (+ storage keys) under ``run_ids``."""
    suite_ids = list(
        session.execute(select(TestSuite.id).where(TestSuite.run_id.in_(run_ids))).scalars()
    )
    case_ids = (
        list(session.execute(select(TestCase.id).where(TestCase.suite_id.in_(suite_ids))).scalars())
        if suite_ids
        else []
    )

    owner = (Artifact.owner_type == "run") & Artifact.owner_id.in_(run_ids)
    if suite_ids:
        owner = owner | ((Artifact.owner_type == "suite") & Artifact.owner_id.in_(suite_ids))
    if case_ids:
        owner = owner | ((Artifact.owner_type == "case") & Artifact.owner_id.in_(case_ids))
    arts = session.execute(select(Artifact.id, Artifact.storage_key).where(owner)).all()
    art_ids = {a for a, _ in arts}
    der = (
        session.execute(
            select(DerivedArtifact.id, DerivedArtifact.storage_key).where(
                DerivedArtifact.source_artifact_id.in_(art_ids)
            )
        ).all()
        if art_ids
        else []
    )
    der_ids = {d for d, _ in der}
    candidate_keys = {k for _, k in arts} | {k for _, k in der}
    return _RunArtifacts(suite_ids, case_ids, art_ids, der_ids, candidate_keys)


def _delete_run_rows(session: Session, run_ids: list[str], ra: _RunArtifacts) -> None:
    """Explicit, FK-safe deletes of all rows under ``run_ids`` (SQLite won't cascade)."""
    if ra.der_ids:
        session.execute(delete(DerivedArtifact).where(DerivedArtifact.id.in_(ra.der_ids)))
    if ra.art_ids:
        session.execute(delete(Artifact).where(Artifact.id.in_(ra.art_ids)))
    report_ids = list(
        session.execute(select(LogReport.id).where(LogReport.run_id.in_(run_ids))).scalars()
    )
    if report_ids:
        session.execute(delete(LogFinding).where(LogFinding.log_report_id.in_(report_ids)))
        session.execute(delete(LogReport).where(LogReport.id.in_(report_ids)))
    if ra.case_ids:
        session.execute(delete(TestCase).where(TestCase.id.in_(ra.case_ids)))
    if ra.suite_ids:
        session.execute(delete(TestSuite).where(TestSuite.id.in_(ra.suite_ids)))
    session.execute(delete(RunTag).where(RunTag.run_id.in_(run_ids)))
    # Surviving runs (e.g. in other projects) may reference a deleted run as
    # their calibration; null it so the FK doesn't dangle.
    session.execute(
        update(TestRun)
        .where(TestRun.calibration_run_id.in_(run_ids))
        .values(calibration_run_id=None)
    )
    session.execute(delete(TestRun).where(TestRun.id.in_(run_ids)))


def _gc_orphan_blobs(session: Session, storage: ObjectStorage, candidate_keys: set[str]) -> int:
    """Commit pending row deletes, then delete any now-unreferenced blobs."""
    # Rows must be gone before we decide a key is orphaned; commit first so a
    # crash leaves a harmless extra blob rather than a row with no blob.
    orphan = _orphan_keys(session, candidate_keys)
    session.commit()
    deleted = 0
    for key in orphan:
        with contextlib.suppress(Exception):  # best-effort; a leftover blob is harmless
            storage.delete(key)
            deleted += 1
    return deleted


def prune_runs(
    session: Session,
    storage: ObjectStorage,
    *,
    cutoff: datetime,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Delete runs created before ``cutoff`` (rows + orphaned blobs)."""
    run_ids = list(session.execute(select(TestRun.id).where(TestRun.created_at < cutoff)).scalars())
    if not run_ids:
        return {"runs": 0, "artifacts": 0, "blobs": 0, "dry_run": dry_run}

    ra = _collect_run_artifacts(session, run_ids)

    if dry_run:
        orphan = _orphan_keys(
            session,
            ra.candidate_keys,
            exclude_artifact_ids=ra.art_ids,
            exclude_derived_ids=ra.der_ids,
        )
        return {
            "runs": len(run_ids),
            "artifacts": len(ra.art_ids),
            "blobs": len(orphan),
            "dry_run": True,
        }

    _delete_run_rows(session, run_ids, ra)
    session.flush()
    deleted = _gc_orphan_blobs(session, storage, ra.candidate_keys)
    return {"runs": len(run_ids), "artifacts": len(ra.art_ids), "blobs": deleted, "dry_run": False}


def delete_project(
    session: Session,
    storage: ObjectStorage,
    *,
    project_id: str,
) -> dict[str, Any]:
    """Delete a project and everything under it.

    Removes all runs (suites/cases/artifacts/logs/tags) and the project-scoped
    specs, saved views, and spectrum masks, then the project row — and GCs any
    content-addressed blob no surviving artifact still references. Returns counts.
    """
    run_ids = list(
        session.execute(select(TestRun.id).where(TestRun.project_id == project_id)).scalars()
    )
    ra = (
        _collect_run_artifacts(session, run_ids)
        if run_ids
        else _RunArtifacts([], [], set(), set(), set())
    )

    if run_ids:
        _delete_run_rows(session, run_ids, ra)
    # Project-scoped rows must go before the project row (FK on Postgres).
    session.execute(delete(SpecDefinition).where(SpecDefinition.project_id == project_id))
    session.execute(delete(SavedView).where(SavedView.project_id == project_id))
    session.execute(delete(SpectrumMask).where(SpectrumMask.project_id == project_id))
    session.execute(delete(Project).where(Project.id == project_id))
    session.flush()

    deleted = _gc_orphan_blobs(session, storage, ra.candidate_keys)
    return {"runs": len(run_ids), "artifacts": len(ra.art_ids), "blobs": deleted}
