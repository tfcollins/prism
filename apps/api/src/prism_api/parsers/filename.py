"""Artifact filename convention parser.

Convention:
    {suite}__{case}__{label}.{ext}   -> case-scoped
    {suite}__{label}.{ext}           -> suite-scoped
    {label}.{ext}                    -> run-scoped
Double-underscore (`__`) separates scope tokens; single underscores are allowed in labels.
"""

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

Scope = Literal["run", "suite", "case"]


@dataclass(frozen=True)
class ArtifactOwner:
    scope: Scope
    suite: str | None
    case: str | None
    label: str
    ext: str


def parse_artifact_filename(filename: str) -> ArtifactOwner:
    p = PurePosixPath(filename)
    ext = p.suffix
    stem = p.name[: -len(ext)] if ext else p.name
    parts = stem.split("__")
    if len(parts) >= 3:
        return ArtifactOwner(
            scope="case", suite=parts[0], case=parts[1], label="__".join(parts[2:]), ext=ext
        )
    if len(parts) == 2:
        return ArtifactOwner(scope="suite", suite=parts[0], case=None, label=parts[1], ext=ext)
    return ArtifactOwner(scope="run", suite=None, case=None, label=parts[0], ext=ext)
