"""Matrix-config repository with defaults + effective-config merge."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from prism_api.models.matrix_config import MatrixConfig

DEFAULT_MATRIX_CONFIG: dict[str, Any] = {
    "row_key": "hw",
    "col_key": "platform",
    "filter_key": "boot_file",
    "curated_rows": [],
    "curated_cols": [],
    "stale_after_hours": 48,
    "refresh_seconds": 30,
    "rotate_filters": [],
}


class MatrixConfigRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, scope: str) -> MatrixConfig | None:
        return self._session.execute(
            select(MatrixConfig).where(MatrixConfig.scope == scope)
        ).scalar_one_or_none()

    def upsert(self, scope: str, config: dict[str, Any]) -> MatrixConfig:
        existing = self.get(scope)
        if existing is not None:
            existing.config = config
            return existing
        row = MatrixConfig(scope=scope, config=config)
        self._session.add(row)
        self._session.flush()
        return row

    def effective(self, scope: str) -> dict[str, Any]:
        """Defaults overlaid with any stored overrides for this scope."""
        merged = dict(DEFAULT_MATRIX_CONFIG)
        row = self.get(scope)
        if row is not None:
            merged.update(row.config)
        return merged
