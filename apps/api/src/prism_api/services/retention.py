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
from prism_api.models.run import RunTag, TestRun
from prism_api.models.suite import TestCase, TestSuite
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


def prune_runs(
    session: Session,
    storage: ObjectStorage,
    *,
    cutoff: datetime,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Delete runs created before ``cutoff`` (rows + orphaned blobs)."""
    run_ids = list(session.execute(select(TestRun.id).where(TestRun.created_at < cutoff)).scalars())
    empty = {"runs": 0, "artifacts": 0, "blobs": 0, "dry_run": dry_run}
    if not run_ids:
        return empty

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

    if dry_run:
        orphan = _orphan_keys(
            session, candidate_keys, exclude_artifact_ids=art_ids, exclude_derived_ids=der_ids
        )
        return {
            "runs": len(run_ids),
            "artifacts": len(art_ids),
            "blobs": len(orphan),
            "dry_run": True,
        }

    # Explicit, FK-safe deletes (SQLite doesn't cascade).
    if der_ids:
        session.execute(delete(DerivedArtifact).where(DerivedArtifact.id.in_(der_ids)))
    if art_ids:
        session.execute(delete(Artifact).where(Artifact.id.in_(art_ids)))
    report_ids = list(
        session.execute(select(LogReport.id).where(LogReport.run_id.in_(run_ids))).scalars()
    )
    if report_ids:
        session.execute(delete(LogFinding).where(LogFinding.log_report_id.in_(report_ids)))
        session.execute(delete(LogReport).where(LogReport.id.in_(report_ids)))
    if case_ids:
        session.execute(delete(TestCase).where(TestCase.id.in_(case_ids)))
    if suite_ids:
        session.execute(delete(TestSuite).where(TestSuite.id.in_(suite_ids)))
    session.execute(delete(RunTag).where(RunTag.run_id.in_(run_ids)))
    # Surviving runs may reference a pruned run as their calibration; null it.
    session.execute(
        update(TestRun)
        .where(TestRun.calibration_run_id.in_(run_ids))
        .values(calibration_run_id=None)
    )
    session.execute(delete(TestRun).where(TestRun.id.in_(run_ids)))
    session.flush()

    # Now that the pruned rows are gone, any candidate key with no remaining
    # reference is safe to delete from object storage.
    orphan = _orphan_keys(session, candidate_keys)
    session.commit()

    deleted = 0
    for key in orphan:
        # best-effort; a leftover blob is harmless
        with contextlib.suppress(Exception):
            storage.delete(key)
            deleted += 1
    return {"runs": len(run_ids), "artifacts": len(art_ids), "blobs": deleted, "dry_run": False}
