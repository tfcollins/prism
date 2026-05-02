"""Artifact and derived-artifact repositories."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from prism_api.models.artifact import Artifact, ArtifactKind, DerivedArtifact, DerivedKind


class ArtifactRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        owner_type: str,
        owner_id: str,
        kind: ArtifactKind,
        filename: str,
        size_bytes: int,
        content_hash: str,
        storage_key: str,
        metadata: dict[str, Any] | None = None,
        manifest_kind: str | None = None,
    ) -> Artifact:
        artifact = Artifact(
            owner_type=owner_type,
            owner_id=owner_id,
            kind=kind,
            filename=filename,
            size_bytes=size_bytes,
            content_hash=content_hash,
            storage_key=storage_key,
            metadata_json=metadata or {},
            manifest_kind=manifest_kind,
        )
        self._session.add(artifact)
        self._session.flush()
        return artifact

    def get_by_id(self, artifact_id: str) -> Artifact | None:
        return self._session.get(Artifact, artifact_id)

    def list_by_owner(self, owner_type: str, owner_id: str) -> list[Artifact]:
        return list(
            self._session.execute(
                select(Artifact)
                .where(Artifact.owner_type == owner_type, Artifact.owner_id == owner_id)
                .order_by(Artifact.created_at)
            ).scalars()
        )


class DerivedRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        source_artifact_id: str,
        kind: DerivedKind,
        storage_key: str,
        params_hash: str,
    ) -> DerivedArtifact:
        d = DerivedArtifact(
            source_artifact_id=source_artifact_id,
            kind=kind,
            storage_key=storage_key,
            params_hash=params_hash,
        )
        self._session.add(d)
        self._session.flush()
        return d

    def find(
        self, *, source_artifact_id: str, kind: DerivedKind, params_hash: str
    ) -> DerivedArtifact | None:
        return self._session.execute(
            select(DerivedArtifact).where(
                DerivedArtifact.source_artifact_id == source_artifact_id,
                DerivedArtifact.kind == kind,
                DerivedArtifact.params_hash == params_hash,
            )
        ).scalar_one_or_none()
