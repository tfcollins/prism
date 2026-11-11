"""Recover optional provenance from retained metadata of older producers."""

from __future__ import annotations

import json
import logging
from pathlib import PurePosixPath
from typing import Any

from sqlalchemy.orm import Session

from prism_api.models.run import TestRun
from prism_api.repos.artifacts import ArtifactRepo
from prism_api.storage import ObjectStorage

logger = logging.getLogger(__name__)


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def hardware_from_session(meta: dict[str, Any]) -> dict[str, Any] | None:
    pre = _object(_object(meta.get("session_pre")).get("labgrid"))
    post = _object(_object(meta.get("session_post")).get("labgrid"))
    hardware = {**pre, **post}
    if not hardware:
        return None
    tags = _object(hardware.get("tags"))
    for field, tag in (("board", "daughter-board"), ("carrier", "carrier")):
        if tag in tags:
            hardware.setdefault(field, tags[tag])
    errors = list(hardware.get("collection_errors", []))
    for key, value in hardware.items():
        if value and (key.endswith("_error") or key == "error"):
            errors.append(str(value))
    if errors:
        hardware["collection_errors"] = list(dict.fromkeys(errors))
    return hardware


def recover_provenance(
    run: TestRun, *, session: Session, storage: ObjectStorage, tags: dict[str, str]
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    ci, hardware = run.ci, run.hardware
    if ci is not None and hardware is not None:
        return ci, hardware
    for artifact in ArtifactRepo(session).list_by_owner("run", run.id):
        basename = PurePosixPath(artifact.filename).name
        if basename not in {"run_meta.json", "hardware.json", "labgrid__metadata.json"} and not (
            basename == "metadata.json" and "labgrid" in artifact.filename
        ):
            continue
        try:
            meta = json.loads(storage.get_bytes(artifact.storage_key))
            if not isinstance(meta, dict):
                continue
            if basename == "hardware.json" or basename.endswith("metadata.json"):
                hardware = hardware or hardware_from_session({"session_pre": {"labgrid": meta}})
            else:
                ci = ci or _object(meta.get("ci")) or None
                hardware = hardware or _object(meta.get("hardware")) or hardware_from_session(meta)
        except Exception:
            # Missing/corrupt historical blobs must not make the run unreadable.
            logger.warning("could not recover provenance from %s", artifact.id, exc_info=True)
    if ci is None:
        url = tags.get("ci_url") or tags.get("github_run_url") or tags.get("run_url")
        if url:
            ci = {"run_url": url}
    if hardware is None:
        hardware = {
            key: tags[key] for key in ("place", "board", "carrier", "exporter") if tags.get(key)
        } or None
    return ci, hardware
