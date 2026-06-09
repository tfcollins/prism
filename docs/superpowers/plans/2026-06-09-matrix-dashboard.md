# Matrix Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a glanceable 2D coverage-matrix dashboard (rows = `hw`, cols = `platform`) showing the latest test status per board/platform, with a boot-file filter, per-project and global-superset scopes, a per-user enable toggle, and a fullscreen kiosk route.

**Architecture:** New FastAPI routers/repos/models slot into Prism's existing router → repo → model layering. The matrix is computed on the fly from the existing `test_runs` + `run_tags` tables (no cache table). Two new tables — a generic per-user settings store and a shared matrix-config store — back the toggle and the curated/threshold config. The React SPA adds a normal page, a chrome-less kiosk page, a shared grid component, react-query hooks, and a settings toggle.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy (strict mypy), Alembic, pytest (SQLite in-memory). React 18, TypeScript, Chakra UI v3, react-query, axios, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-06-09-matrix-dashboard-design.md`

**Conventions for every task:**
- Backend commands run from `apps/api/`. Frontend commands run from `apps/web/`.
- `uv run pytest <path> -v` for a single backend test; `npx vitest run <path>` for a single frontend test.
- After each task, lint must stay green: backend `uv run ruff check . && uv run mypy src`; frontend `npm run lint`.
- Commit at the end of each task with the message shown.

---

## File Structure

**Backend (`apps/api/src/prism_api/`):**
- `models/user_settings.py` — `UserSetting` (generic per-user key/JSON store).
- `models/matrix_config.py` — `MatrixConfig` (shared config per scope).
- `repos/user_settings.py` — `UserSettingsRepo` (get/upsert).
- `repos/matrix_config.py` — `MatrixConfigRepo` + `DEFAULT_MATRIX_CONFIG` + effective-config merge.
- `repos/matrix.py` — `MatrixRepo.compute(...)` (latest-per-cell aggregation).
- `schemas/user_settings.py` — request/response models for settings.
- `schemas/matrix.py` — request/response models for the matrix + config.
- `routers/user_settings.py` — `/api/v1/me/settings/{key}` GET/PUT.
- `routers/matrix.py` — `/api/v1/matrix` GET, `/api/v1/matrix/config` GET/PUT.
- `migrations/versions/0014_user_settings.py`, `0015_matrix_config.py`.
- `models/__init__.py` — register the two new models.
- `main.py` — wire the two new routers.

**Backend tests (`apps/api/tests/`):**
- `test_user_settings.py`, `test_matrix_config.py`, `test_matrix_repo.py`, `test_matrix_router.py`.

**Frontend (`apps/web/src/`):**
- `api/types.ts` — add matrix + settings types.
- `api/queries.ts` — add hooks.
- `components/MatrixGrid.tsx` + `components/MatrixGrid.test.tsx` — shared grid renderer.
- `pages/MatrixDashboardPage.tsx` — normal page (uses `AppShell`).
- `pages/MatrixKioskPage.tsx` — fullscreen page (no `AppShell`).
- `pages/MatrixDashboardPage.test.tsx` — page smoke test.
- `components/Sidebar.tsx` — conditional Matrix nav entry.
- `pages/MatrixSettingsCard.tsx` — enable toggle + prefs (rendered on an existing settings-ish page; mounted on Tokens page area).
- `App.tsx` — routes `/matrix`, `/projects/:slug/matrix`, `/kiosk/matrix`.
- `pages/AdminPage.tsx` — minimal matrix-config form (new `MatrixConfigTab`).

**Frontend e2e (`apps/web/e2e/`):**
- `matrix.spec.ts`.

**Other:**
- `apps/api/scripts/seed_demo.py` — emit `hw`/`platform`/`boot_file`/`kuiper-linux-release` tags.
- `docs/source/how-to/matrix-dashboard.md` — usage + kiosk how-to.

---

## Task 1: `UserSetting` model + migration

**Files:**
- Create: `apps/api/src/prism_api/models/user_settings.py`
- Modify: `apps/api/src/prism_api/models/__init__.py`
- Create: `apps/api/src/prism_api/migrations/versions/0014_user_settings.py`
- Test: `apps/api/tests/test_user_settings.py`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_user_settings.py`:

```python
"""UserSetting model + repo."""

from prism_api.models.user_settings import UserSetting


def test_user_setting_round_trips_json(db_session):
    db_session.add(UserSetting(user_id="u1", key="matrix_dashboard", value={"enabled": True}))
    db_session.flush()
    got = db_session.get(UserSetting, ("u1", "matrix_dashboard"))
    assert got is not None
    assert got.value == {"enabled": True}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_user_settings.py::test_user_setting_round_trips_json -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prism_api.models.user_settings'`

- [ ] **Step 3: Create the model**

Create `apps/api/src/prism_api/models/user_settings.py`:

```python
"""Generic per-user settings: (user_id, key) -> JSON value."""

from typing import Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from prism_api.models.base import Base, TimestampMixin

_JSON = JSONB().with_variant(JSON(), "sqlite")


class UserSetting(Base, TimestampMixin):
    __tablename__ = "user_settings"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False, default=dict)
```

- [ ] **Step 4: Register the model**

In `apps/api/src/prism_api/models/__init__.py`, add the import (alphabetical-ish, after `user`) and the `__all__` entry:

```python
from prism_api.models.user_settings import UserSetting
```

Add `"UserSetting",` to the `__all__` list.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_user_settings.py -v`
Expected: PASS

- [ ] **Step 6: Create the migration**

Create `apps/api/src/prism_api/migrations/versions/0014_user_settings.py`:

```python
"""add user_settings table

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.String(length=36), primary_key=True),
        sa.Column("key", sa.String(length=100), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("user_settings")
```

- [ ] **Step 7: Verify migration applies (sqlite smoke)**

Run: `uv run alembic upgrade head && uv run alembic downgrade 0013 && uv run alembic upgrade head`
Expected: no errors (the default dev DB or a throwaway sqlite URL; if alembic targets postgres and it isn't running, skip this and rely on the model test).

- [ ] **Step 8: Lint**

Run: `uv run ruff check . && uv run mypy src`
Expected: no errors.

- [ ] **Step 9: Commit**

```bash
git add apps/api/src/prism_api/models/user_settings.py apps/api/src/prism_api/models/__init__.py apps/api/src/prism_api/migrations/versions/0014_user_settings.py apps/api/tests/test_user_settings.py
git commit -m "feat(api): add user_settings table and model"
```

---

## Task 2: `UserSettingsRepo`

**Files:**
- Create: `apps/api/src/prism_api/repos/user_settings.py`
- Test: `apps/api/tests/test_user_settings.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `apps/api/tests/test_user_settings.py`:

```python
from prism_api.repos.user_settings import UserSettingsRepo


def test_repo_get_missing_returns_none(db_session):
    assert UserSettingsRepo(db_session).get("nobody", "matrix_dashboard") is None


def test_repo_upsert_inserts_then_updates(db_session):
    repo = UserSettingsRepo(db_session)
    repo.upsert("u1", "matrix_dashboard", {"enabled": False})
    db_session.flush()
    repo.upsert("u1", "matrix_dashboard", {"enabled": True, "rotate": True})
    db_session.flush()
    got = repo.get("u1", "matrix_dashboard")
    assert got is not None
    assert got.value == {"enabled": True, "rotate": True}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_user_settings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prism_api.repos.user_settings'`

- [ ] **Step 3: Create the repo**

Create `apps/api/src/prism_api/repos/user_settings.py`:

```python
"""Per-user settings repository."""

from typing import Any

from sqlalchemy.orm import Session

from prism_api.models.user_settings import UserSetting


class UserSettingsRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: str, key: str) -> UserSetting | None:
        return self._session.get(UserSetting, (user_id, key))

    def upsert(self, user_id: str, key: str, value: dict[str, Any]) -> UserSetting:
        existing = self.get(user_id, key)
        if existing is not None:
            existing.value = value
            return existing
        row = UserSetting(user_id=user_id, key=key, value=value)
        self._session.add(row)
        return row
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_user_settings.py -v`
Expected: PASS

- [ ] **Step 5: Lint**

Run: `uv run ruff check . && uv run mypy src`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/prism_api/repos/user_settings.py apps/api/tests/test_user_settings.py
git commit -m "feat(api): add UserSettingsRepo"
```

---

## Task 3: User-settings router

**Files:**
- Create: `apps/api/src/prism_api/schemas/user_settings.py`
- Create: `apps/api/src/prism_api/routers/user_settings.py`
- Modify: `apps/api/src/prism_api/main.py`
- Test: `apps/api/tests/test_user_settings.py` (extend with HTTP tests)

- [ ] **Step 1: Write the failing test**

Append to `apps/api/tests/test_user_settings.py`:

```python
def _login(client, db_session, settings):
    from prism_api.auth import hash_password
    from prism_api.repos.users import UserRepo

    UserRepo(db_session).create(email=settings.admin_email or "admin@x.com",
                                password_hash=hash_password("pw"))
    db_session.commit()
    r = client.post("/api/v1/auth/login",
                    json={"email": settings.admin_email or "admin@x.com", "password": "pw"})
    assert r.status_code == 200


def test_get_missing_setting_returns_404(client, db_session, settings):
    _login(client, db_session, settings)
    r = client.get("/api/v1/me/settings/matrix_dashboard")
    assert r.status_code == 404


def test_put_then_get_setting(client, db_session, settings):
    _login(client, db_session, settings)
    csrf = client.cookies.get("prism_csrf")
    r = client.put(
        "/api/v1/me/settings/matrix_dashboard",
        json={"value": {"enabled": True, "rotate": False}},
        headers={"X-Prism-Csrf": csrf},
    )
    assert r.status_code == 200
    assert r.json()["value"] == {"enabled": True, "rotate": False}
    r2 = client.get("/api/v1/me/settings/matrix_dashboard")
    assert r2.json()["value"]["enabled"] is True


def test_put_requires_csrf(client, db_session, settings):
    _login(client, db_session, settings)
    r = client.put("/api/v1/me/settings/matrix_dashboard", json={"value": {"enabled": True}})
    assert r.status_code == 403
```

> Note: confirm the login route shape against `routers/auth.py` (`POST /api/v1/auth/login`). If the field names differ, mirror an existing auth test in `tests/`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_user_settings.py -v`
Expected: FAIL — 404 route not found / module missing.

- [ ] **Step 3: Create the schemas**

Create `apps/api/src/prism_api/schemas/user_settings.py`:

```python
"""User-settings request/response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class UserSettingIn(BaseModel):
    value: dict[str, Any]


class UserSettingOut(BaseModel):
    key: str
    value: dict[str, Any]
    updated_at: datetime
```

- [ ] **Step 4: Create the router**

Create `apps/api/src/prism_api/routers/user_settings.py`:

```python
"""Per-user settings endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from prism_api.deps import csrf_protect, current_user, session_dep
from prism_api.models.user import User
from prism_api.repos.user_settings import UserSettingsRepo
from prism_api.schemas.user_settings import UserSettingIn, UserSettingOut

router = APIRouter(prefix="/api/v1/me/settings", tags=["user-settings"])


@router.get("/{key}")
def get_setting(
    key: str,
    user: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> UserSettingOut:
    row = UserSettingsRepo(session).get(user.id, key)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "setting not found")
    return UserSettingOut(key=row.key, value=row.value, updated_at=row.updated_at)


@router.put("/{key}", dependencies=[Depends(csrf_protect)])
def put_setting(
    key: str,
    body: UserSettingIn,
    user: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> UserSettingOut:
    row = UserSettingsRepo(session).upsert(user.id, key, body.value)
    session.flush()
    return UserSettingOut(key=row.key, value=row.value, updated_at=row.updated_at)
```

- [ ] **Step 5: Wire the router**

In `apps/api/src/prism_api/main.py`, add the import alongside the others:

```python
from prism_api.routers import user_settings as user_settings_router
```

and register it with the rest:

```python
app.include_router(user_settings_router.router)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_user_settings.py -v`
Expected: PASS

- [ ] **Step 7: Lint**

Run: `uv run ruff check . && uv run mypy src`
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/prism_api/schemas/user_settings.py apps/api/src/prism_api/routers/user_settings.py apps/api/src/prism_api/main.py apps/api/tests/test_user_settings.py
git commit -m "feat(api): add /me/settings endpoints"
```

---

## Task 4: `MatrixConfig` model + migration

**Files:**
- Create: `apps/api/src/prism_api/models/matrix_config.py`
- Modify: `apps/api/src/prism_api/models/__init__.py`
- Create: `apps/api/src/prism_api/migrations/versions/0015_matrix_config.py`
- Test: `apps/api/tests/test_matrix_config.py`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_matrix_config.py`:

```python
"""MatrixConfig model + repo."""

from prism_api.models.matrix_config import MatrixConfig


def test_matrix_config_round_trips(db_session):
    db_session.add(MatrixConfig(scope="global", config={"stale_after_hours": 24}))
    db_session.flush()
    rows = db_session.query(MatrixConfig).all()
    assert rows[0].scope == "global"
    assert rows[0].config == {"stale_after_hours": 24}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_matrix_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prism_api.models.matrix_config'`

- [ ] **Step 3: Create the model**

Create `apps/api/src/prism_api/models/matrix_config.py`:

```python
"""Shared matrix-dashboard config, keyed by scope ('global' or 'project:<slug>')."""

import uuid
from typing import Any

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from prism_api.models.base import Base, TimestampMixin

_JSON = JSONB().with_variant(JSON(), "sqlite")


class MatrixConfig(Base, TimestampMixin):
    __tablename__ = "matrix_config"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scope: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False, default=dict)

    __table_args__ = (UniqueConstraint("scope", name="uq_matrix_config_scope"),)
```

- [ ] **Step 4: Register the model**

In `apps/api/src/prism_api/models/__init__.py`, add:

```python
from prism_api.models.matrix_config import MatrixConfig
```

and add `"MatrixConfig",` to `__all__`.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_matrix_config.py -v`
Expected: PASS

- [ ] **Step 6: Create the migration**

Create `apps/api/src/prism_api/migrations/versions/0015_matrix_config.py`:

```python
"""add matrix_config table

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "matrix_config",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("scope", sa.String(length=255), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("scope", name="uq_matrix_config_scope"),
    )


def downgrade() -> None:
    op.drop_table("matrix_config")
```

- [ ] **Step 7: Lint**

Run: `uv run ruff check . && uv run mypy src`
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/prism_api/models/matrix_config.py apps/api/src/prism_api/models/__init__.py apps/api/src/prism_api/migrations/versions/0015_matrix_config.py apps/api/tests/test_matrix_config.py
git commit -m "feat(api): add matrix_config table and model"
```

---

## Task 5: `MatrixConfigRepo` + defaults + effective merge

**Files:**
- Create: `apps/api/src/prism_api/repos/matrix_config.py`
- Test: `apps/api/tests/test_matrix_config.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `apps/api/tests/test_matrix_config.py`:

```python
from prism_api.repos.matrix_config import DEFAULT_MATRIX_CONFIG, MatrixConfigRepo


def test_effective_returns_defaults_when_absent(db_session):
    eff = MatrixConfigRepo(db_session).effective("global")
    assert eff == DEFAULT_MATRIX_CONFIG


def test_effective_merges_overrides_over_defaults(db_session):
    repo = MatrixConfigRepo(db_session)
    repo.upsert("global", {"stale_after_hours": 24, "curated_rows": ["ad9152"]})
    db_session.flush()
    eff = repo.effective("global")
    assert eff["stale_after_hours"] == 24
    assert eff["curated_rows"] == ["ad9152"]
    # untouched keys fall back to defaults
    assert eff["row_key"] == DEFAULT_MATRIX_CONFIG["row_key"]
    assert eff["refresh_seconds"] == DEFAULT_MATRIX_CONFIG["refresh_seconds"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_matrix_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prism_api.repos.matrix_config'`

- [ ] **Step 3: Create the repo + defaults**

Create `apps/api/src/prism_api/repos/matrix_config.py`:

```python
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
        return row

    def effective(self, scope: str) -> dict[str, Any]:
        """Defaults overlaid with any stored overrides for this scope."""
        merged = dict(DEFAULT_MATRIX_CONFIG)
        row = self.get(scope)
        if row is not None:
            merged.update(row.config)
        return merged
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_matrix_config.py -v`
Expected: PASS

- [ ] **Step 5: Lint**

Run: `uv run ruff check . && uv run mypy src`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/prism_api/repos/matrix_config.py apps/api/tests/test_matrix_config.py
git commit -m "feat(api): add MatrixConfigRepo with defaults and effective merge"
```

---

## Task 6: Matrix schemas

**Files:**
- Create: `apps/api/src/prism_api/schemas/matrix.py`
- Test: covered indirectly by Task 8; no standalone test needed (pure pydantic).

- [ ] **Step 1: Create the schemas**

Create `apps/api/src/prism_api/schemas/matrix.py`:

```python
"""Matrix dashboard request/response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class MatrixCell(BaseModel):
    status: str  # RunStatus value: pass/fail/mixed/error
    run_id: str
    passed: int
    total: int
    finished_at: datetime | None
    age_seconds: int
    stale: bool


class MatrixResponse(BaseModel):
    scope: str
    generated_at: datetime
    row_key: str
    col_key: str
    rows: list[str]
    cols: list[str]
    boot_files: list[str]
    stale_after_hours: int
    summary: dict[str, int]
    unplaced_runs: int
    cells: dict[str, MatrixCell]


class MatrixConfigBody(BaseModel):
    row_key: str = "hw"
    col_key: str = "platform"
    filter_key: str = "boot_file"
    curated_rows: list[str] = []
    curated_cols: list[str] = []
    stale_after_hours: int = 48
    refresh_seconds: int = 30
    rotate_filters: list[str] = []


class MatrixConfigOut(BaseModel):
    scope: str
    config: dict[str, Any]
```

> Note on the `pass` key: `pass` is a Python keyword, so the summary is typed as a plain `dict[str, int]` rather than a pydantic model with a `pass` field. The repo (Task 7) emits a dict with keys `pass`/`fail`/`mixed`/`error`/`no_run`.

- [ ] **Step 2: Lint**

Run: `uv run ruff check . && uv run mypy src`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add apps/api/src/prism_api/schemas/matrix.py
git commit -m "feat(api): add matrix schemas"
```

---

## Task 7: `MatrixRepo.compute` — the core aggregation

**Files:**
- Create: `apps/api/src/prism_api/repos/matrix.py`
- Test: `apps/api/tests/test_matrix_repo.py`

The computation is done in Python after a few simple selects, so it runs identically on SQLite (tests) and Postgres (prod). No dialect-specific SQL.

- [ ] **Step 1: Write the failing test (latest-per-cell + no-run + summary)**

Create `apps/api/tests/test_matrix_repo.py`:

```python
"""MatrixRepo.compute aggregation."""

from datetime import UTC, datetime, timedelta

from prism_api.models.project import Project
from prism_api.models.run import RunStatus, RunTag, TestRun
from prism_api.models.suite import TestSuite
from prism_api.repos.matrix import MatrixRepo
from prism_api.repos.matrix_config import DEFAULT_MATRIX_CONFIG


def _run(session, project_id, *, name, status, finished_at, tags, counts=(1, 0)):
    run = TestRun(project_id=project_id, name=name, status=status, finished_at=finished_at)
    session.add(run)
    session.flush()
    for k, v in tags.items():
        session.add(RunTag(run_id=run.id, key=k, value=v))
    passed, failed = counts
    session.add(
        TestSuite(
            run_id=run.id, name="s", pass_count=passed, fail_count=failed,
            error_count=0, skip_count=0, duration_ms=0,
        )
    )
    session.flush()
    return run


def _project(session, slug="kuiper-linux"):
    p = Project(slug=slug, name=slug)
    session.add(p)
    session.flush()
    return p


def test_compute_picks_latest_run_per_cell(db_session):
    p = _project(db_session)
    now = datetime.now(UTC)
    _run(db_session, p.id, name="old", status=RunStatus.FAIL,
         finished_at=now - timedelta(hours=2),
         tags={"hw": "ad9081", "platform": "zcu102"}, counts=(8, 4))
    newer = _run(db_session, p.id, name="new", status=RunStatus.PASS,
                 finished_at=now - timedelta(minutes=5),
                 tags={"hw": "ad9081", "platform": "zcu102"}, counts=(12, 0))
    db_session.flush()

    res = MatrixRepo(db_session).compute(
        scope="project:kuiper-linux", boot_files=[], config=DEFAULT_MATRIX_CONFIG
    )
    cell = res["cells"]["ad9081|zcu102"]
    assert cell["run_id"] == newer.id
    assert cell["status"] == "pass"
    assert (cell["passed"], cell["total"]) == (12, 12)
    assert res["rows"] == ["ad9081"]
    assert res["cols"] == ["zcu102"]
    assert res["summary"]["pass"] == 1


def test_compute_marks_stale(db_session):
    p = _project(db_session)
    now = datetime.now(UTC)
    _run(db_session, p.id, name="r", status=RunStatus.PASS,
         finished_at=now - timedelta(hours=72),
         tags={"hw": "ad9081", "platform": "zcu102"})
    db_session.flush()
    res = MatrixRepo(db_session).compute(
        scope="project:kuiper-linux", boot_files=[],
        config={**DEFAULT_MATRIX_CONFIG, "stale_after_hours": 48},
    )
    assert res["cells"]["ad9081|zcu102"]["stale"] is True


def test_compute_boot_file_filter(db_session):
    p = _project(db_session)
    now = datetime.now(UTC)
    _run(db_session, p.id, name="zmp", status=RunStatus.PASS, finished_at=now,
         tags={"hw": "ad9081", "platform": "zcu102", "boot_file": "zynqmp-common"})
    _run(db_session, p.id, name="zq", status=RunStatus.FAIL, finished_at=now,
         tags={"hw": "ad9371", "platform": "zed", "boot_file": "zynq-common"})
    db_session.flush()
    res = MatrixRepo(db_session).compute(
        scope="project:kuiper-linux", boot_files=["zynqmp-common"], config=DEFAULT_MATRIX_CONFIG
    )
    assert "ad9081|zcu102" in res["cells"]
    assert "ad9371|zed" not in res["cells"]
    assert sorted(res["boot_files"]) == ["zynq-common", "zynqmp-common"]


def test_compute_curated_extras_add_empty_rows_cols(db_session):
    p = _project(db_session)
    _run(db_session, p.id, name="r", status=RunStatus.PASS, finished_at=datetime.now(UTC),
         tags={"hw": "ad9081", "platform": "zcu102"})
    db_session.flush()
    res = MatrixRepo(db_session).compute(
        scope="project:kuiper-linux", boot_files=[],
        config={**DEFAULT_MATRIX_CONFIG, "curated_rows": ["ad9152"], "curated_cols": ["vcu118"]},
    )
    assert res["rows"] == ["ad9081", "ad9152"]
    assert res["cols"] == ["vcu118", "zcu102"]
    # one real cell + (2 rows x 2 cols - 1) = 3 no-run intersections
    assert res["summary"]["no_run"] == 3


def test_compute_unplaced_runs_counted(db_session):
    p = _project(db_session)
    now = datetime.now(UTC)
    _run(db_session, p.id, name="ok", status=RunStatus.PASS, finished_at=now,
         tags={"hw": "ad9081", "platform": "zcu102"})
    _run(db_session, p.id, name="nohw", status=RunStatus.PASS, finished_at=now,
         tags={"platform": "zcu102"})
    db_session.flush()
    res = MatrixRepo(db_session).compute(
        scope="project:kuiper-linux", boot_files=[], config=DEFAULT_MATRIX_CONFIG
    )
    assert res["unplaced_runs"] == 1


def test_compute_global_superset_by_release_tag(db_session):
    pa = _project(db_session, slug="proj-a")
    pb = _project(db_session, slug="proj-b")
    now = datetime.now(UTC)
    _run(db_session, pa.id, name="a", status=RunStatus.PASS, finished_at=now,
         tags={"hw": "ad9081", "platform": "zcu102", "kuiper-linux-release": "2024_R2"})
    _run(db_session, pb.id, name="b", status=RunStatus.FAIL, finished_at=now,
         tags={"hw": "ad9371", "platform": "zed", "kuiper-linux-release": "2024_R2"})
    _run(db_session, pb.id, name="untagged", status=RunStatus.PASS, finished_at=now,
         tags={"hw": "adrv9009", "platform": "zed"})  # no release tag → excluded
    db_session.flush()
    res = MatrixRepo(db_session).compute(
        scope="global", boot_files=[], config=DEFAULT_MATRIX_CONFIG
    )
    assert set(res["rows"]) == {"ad9081", "ad9371"}
    assert "adrv9009" not in res["rows"]
```

> Note: confirm `TestSuite`'s column names (`pass_count`, `fail_count`, `error_count`, `skip_count`, `duration_ms`) against `models/suite.py` before running; adjust the `_run` helper if they differ.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_matrix_repo.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prism_api.repos.matrix'`

- [ ] **Step 3: Create the repo**

Create `apps/api/src/prism_api/repos/matrix.py`:

```python
"""Matrix dashboard computation: latest run per (row, col) cell."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from prism_api.models.project import Project
from prism_api.models.run import RunStatus, RunTag, TestRun
from prism_api.repos.runs import RunRepo

RELEASE_TAG_KEY = "kuiper-linux-release"


class MatrixRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _candidate_runs(self, scope: str) -> list[TestRun]:
        if scope == "global":
            sub = select(RunTag.run_id).where(RunTag.key == RELEASE_TAG_KEY)
            stmt = select(TestRun).where(TestRun.id.in_(sub))
            return list(self._session.execute(stmt).scalars())
        if scope.startswith("project:"):
            slug = scope.split(":", 1)[1]
            proj = self._session.execute(
                select(Project).where(Project.slug == slug)
            ).scalar_one_or_none()
            if proj is None:
                return []
            stmt = select(TestRun).where(TestRun.project_id == proj.id)
            return list(self._session.execute(stmt).scalars())
        return []

    def _tags_by_run(self, run_ids: list[str], keys: list[str]) -> dict[str, dict[str, str]]:
        if not run_ids:
            return {}
        rows = self._session.execute(
            select(RunTag.run_id, RunTag.key, RunTag.value).where(
                RunTag.run_id.in_(run_ids), RunTag.key.in_(keys)
            )
        ).all()
        out: dict[str, dict[str, str]] = {}
        for run_id, key, value in rows:
            out.setdefault(run_id, {})[key] = value
        return out

    @staticmethod
    def _sort_key(run: TestRun) -> tuple[datetime, datetime, str]:
        finished = run.finished_at or run.created_at
        return (finished, run.created_at, run.id)

    def compute(
        self, *, scope: str, boot_files: list[str], config: dict[str, Any]
    ) -> dict[str, Any]:
        row_key = config["row_key"]
        col_key = config["col_key"]
        filter_key = config["filter_key"]
        stale_after_hours = int(config["stale_after_hours"])

        runs = self._candidate_runs(scope)
        # Ignore runs that never completed.
        runs = [r for r in runs if r.status != RunStatus.PENDING]
        tags = self._tags_by_run([r.id for r in runs], [row_key, col_key, filter_key])

        # Available boot-file values (before applying the filter) for the filter bar.
        boot_file_values = sorted(
            {tags.get(r.id, {}).get(filter_key) for r in runs} - {None}  # type: ignore[arg-type]
        )

        # Apply boot-file filter.
        if boot_files:
            wanted = set(boot_files)
            runs = [r for r in runs if tags.get(r.id, {}).get(filter_key) in wanted]

        # Split placeable vs unplaced.
        placeable: list[TestRun] = []
        unplaced = 0
        for r in runs:
            t = tags.get(r.id, {})
            if t.get(row_key) and t.get(col_key):
                placeable.append(r)
            else:
                unplaced += 1

        # Latest run per (row, col).
        latest: dict[tuple[str, str], TestRun] = {}
        for r in sorted(placeable, key=self._sort_key, reverse=True):
            t = tags[r.id]
            cellkey = (t[row_key], t[col_key])
            if cellkey not in latest:
                latest[cellkey] = r

        observed_rows = {k[0] for k in latest}
        observed_cols = {k[1] for k in latest}
        rows = sorted(observed_rows | set(config.get("curated_rows", [])))
        cols = sorted(observed_cols | set(config.get("curated_cols", [])))

        now = datetime.now(UTC)
        run_repo = RunRepo(self._session)
        cells: dict[str, dict[str, Any]] = {}
        for (rv, cv), run in latest.items():
            counts = run_repo.aggregate_counts_by_run(run.id)
            total = (
                counts["pass_count"]
                + counts["fail_count"]
                + counts["error_count"]
                + counts["skip_count"]
            )
            finished = run.finished_at or run.created_at
            if finished.tzinfo is None:
                finished = finished.replace(tzinfo=UTC)
            age_seconds = int((now - finished).total_seconds())
            cells[f"{rv}|{cv}"] = {
                "status": str(run.status),
                "run_id": run.id,
                "passed": counts["pass_count"],
                "total": total,
                "finished_at": run.finished_at,
                "age_seconds": age_seconds,
                "stale": age_seconds > stale_after_hours * 3600,
            }

        summary = {"pass": 0, "fail": 0, "mixed": 0, "error": 0, "no_run": 0}
        for rv in rows:
            for cv in cols:
                cell = cells.get(f"{rv}|{cv}")
                if cell is None:
                    summary["no_run"] += 1
                else:
                    summary[cell["status"]] = summary.get(cell["status"], 0) + 1

        return {
            "scope": scope,
            "generated_at": now,
            "row_key": row_key,
            "col_key": col_key,
            "rows": rows,
            "cols": cols,
            "boot_files": boot_file_values,
            "stale_after_hours": stale_after_hours,
            "summary": summary,
            "unplaced_runs": unplaced,
            "cells": cells,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_matrix_repo.py -v`
Expected: PASS (all six tests).

- [ ] **Step 5: Lint**

Run: `uv run ruff check . && uv run mypy src`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/prism_api/repos/matrix.py apps/api/tests/test_matrix_repo.py
git commit -m "feat(api): add MatrixRepo latest-per-cell computation"
```

---

## Task 8: Matrix router (read + config)

**Files:**
- Create: `apps/api/src/prism_api/routers/matrix.py`
- Modify: `apps/api/src/prism_api/main.py`
- Test: `apps/api/tests/test_matrix_router.py`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_matrix_router.py`:

```python
"""Matrix router HTTP tests."""

from datetime import UTC, datetime

from prism_api.auth import hash_password
from prism_api.models.project import Project
from prism_api.models.run import RunStatus, RunTag, TestRun
from prism_api.models.suite import TestSuite
from prism_api.repos.users import UserRepo


def _login(client, db_session, settings, *, admin=True):
    email = settings.admin_email if admin and settings.admin_email else "admin@x.com"
    UserRepo(db_session).create(email=email, password_hash=hash_password("pw"))
    db_session.commit()
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "pw"})
    assert r.status_code == 200
    return email


def _seed_cell(db_session):
    p = Project(slug="kuiper-linux", name="Kuiper")
    db_session.add(p)
    db_session.flush()
    run = TestRun(project_id=p.id, name="r", status=RunStatus.PASS, finished_at=datetime.now(UTC))
    db_session.add(run)
    db_session.flush()
    db_session.add_all([
        RunTag(run_id=run.id, key="hw", value="ad9081"),
        RunTag(run_id=run.id, key="platform", value="zcu102"),
        TestSuite(run_id=run.id, name="s", pass_count=5, fail_count=0,
                  error_count=0, skip_count=0, duration_ms=0),
    ])
    db_session.commit()


def test_matrix_read_requires_auth(client):
    assert client.get("/api/v1/matrix?scope=project:kuiper-linux").status_code == 401


def test_matrix_read_returns_grid(client, db_session, settings):
    _login(client, db_session, settings)
    _seed_cell(db_session)
    r = client.get("/api/v1/matrix?scope=project:kuiper-linux")
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == ["ad9081"]
    assert body["cells"]["ad9081|zcu102"]["status"] == "pass"


def test_config_get_returns_defaults(client, db_session, settings):
    _login(client, db_session, settings)
    r = client.get("/api/v1/matrix/config?scope=global")
    assert r.status_code == 200
    assert r.json()["config"]["stale_after_hours"] == 48


def test_config_put_admin_only(client, db_session, settings):
    # Log in as a NON-admin (settings.admin_email differs from this user).
    UserRepo(db_session).create(email="user@x.com", password_hash=hash_password("pw"))
    db_session.commit()
    assert client.post("/api/v1/auth/login",
                       json={"email": "user@x.com", "password": "pw"}).status_code == 200
    csrf = client.cookies.get("prism_csrf")
    r = client.put("/api/v1/matrix/config?scope=global",
                   json={"stale_after_hours": 24}, headers={"X-Prism-Csrf": csrf})
    assert r.status_code == 403


def test_config_put_then_get(client, db_session, settings):
    _login(client, db_session, settings)
    csrf = client.cookies.get("prism_csrf")
    r = client.put("/api/v1/matrix/config?scope=global",
                   json={"stale_after_hours": 24}, headers={"X-Prism-Csrf": csrf})
    assert r.status_code == 200
    assert client.get("/api/v1/matrix/config?scope=global").json()["config"]["stale_after_hours"] == 24
```

- [ ] **Step 2: Ensure the test settings define an admin email**

The admin-only tests require `settings.admin_email` to be set (so `require_admin` recognizes the logged-in admin). In `apps/api/tests/conftest.py`, add `admin_email="admin@x.com"` to the `settings` fixture's `Settings(...)` call:

```python
    return Settings(  # type: ignore[call-arg]
        database_url="sqlite:///:memory:",
        s3_endpoint="x",
        s3_access_key="x",
        s3_secret_key="x",
        s3_bucket="x",
        redis_url="x",
        jwt_secret="testsecretlongenough",
        admin_email="admin@x.com",
    )
```

> Confirm `Settings` has an `admin_email` field (see `config.py`). The non-admin test relies on `settings.admin_email != "user@x.com"`, which holds with this value.

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_matrix_router.py -v`
Expected: FAIL — route not found / module missing.

- [ ] **Step 4: Create the router**

Create `apps/api/src/prism_api/routers/matrix.py`:

```python
"""Matrix dashboard endpoints: read grid + admin config."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from prism_api.deps import csrf_protect, current_user, require_admin, session_dep
from prism_api.models.user import User
from prism_api.repos.matrix import MatrixRepo
from prism_api.repos.matrix_config import MatrixConfigRepo
from prism_api.schemas.matrix import MatrixConfigBody, MatrixConfigOut, MatrixResponse

router = APIRouter(prefix="/api/v1/matrix", tags=["matrix"])


@router.get("")
def get_matrix(
    scope: str,
    boot_file: Annotated[list[str], Query()] = [],  # noqa: B006 - FastAPI query default
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> MatrixResponse:
    config = MatrixConfigRepo(session).effective(scope)
    result = MatrixRepo(session).compute(scope=scope, boot_files=boot_file, config=config)
    return MatrixResponse(**result)


@router.get("/config")
def get_config(
    scope: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> MatrixConfigOut:
    config = MatrixConfigRepo(session).effective(scope)
    return MatrixConfigOut(scope=scope, config=config)


@router.put("/config", dependencies=[Depends(csrf_protect), Depends(require_admin)])
def put_config(
    scope: str,
    body: MatrixConfigBody,
    session: Session = Depends(session_dep),
) -> MatrixConfigOut:
    repo = MatrixConfigRepo(session)
    row = repo.upsert(scope, body.model_dump())
    session.flush()
    return MatrixConfigOut(scope=scope, config=row.config)
```

- [ ] **Step 5: Wire the router**

In `apps/api/src/prism_api/main.py`, add the import:

```python
from prism_api.routers import matrix as matrix_router
```

and register it:

```python
app.include_router(matrix_router.router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_matrix_router.py -v`
Expected: PASS

- [ ] **Step 7: Run the full backend suite**

Run: `uv run pytest`
Expected: PASS (no regressions).

- [ ] **Step 8: Lint**

Run: `uv run ruff check . && uv run mypy src`
Expected: no errors.

- [ ] **Step 9: Commit**

```bash
git add apps/api/src/prism_api/routers/matrix.py apps/api/src/prism_api/main.py apps/api/tests/test_matrix_router.py
git commit -m "feat(api): add /matrix read and config endpoints"
```

---

## Task 9: Frontend types

**Files:**
- Modify: `apps/web/src/api/types.ts`

- [ ] **Step 1: Add types**

Append to `apps/web/src/api/types.ts`:

```typescript
export interface MatrixCell {
  status: RunStatus;
  run_id: string;
  passed: number;
  total: number;
  finished_at: string | null;
  age_seconds: number;
  stale: boolean;
}

export interface MatrixResponse {
  scope: string;
  generated_at: string;
  row_key: string;
  col_key: string;
  rows: string[];
  cols: string[];
  boot_files: string[];
  stale_after_hours: number;
  summary: Record<string, number>;
  unplaced_runs: number;
  cells: Record<string, MatrixCell>;
}

export interface MatrixConfig {
  row_key: string;
  col_key: string;
  filter_key: string;
  curated_rows: string[];
  curated_cols: string[];
  stale_after_hours: number;
  refresh_seconds: number;
  rotate_filters: string[];
}

export interface MatrixConfigOut {
  scope: string;
  config: MatrixConfig;
}

export interface MatrixDashboardPrefs {
  enabled: boolean;
  default_scope?: string;
  boot_file_filter?: string[];
  rotate?: boolean;
}

export interface UserSettingOut {
  key: string;
  value: Record<string, unknown>;
  updated_at: string;
}
```

- [ ] **Step 2: Typecheck**

Run: `npm run build`
Expected: `tsc --noEmit` passes (no usages yet, so just compiles).

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/api/types.ts
git commit -m "feat(web): add matrix dashboard types"
```

---

## Task 10: react-query hooks

**Files:**
- Modify: `apps/web/src/api/queries.ts`

- [ ] **Step 1: Add hooks**

Append to `apps/web/src/api/queries.ts` (imports `api`, `useQuery`, `useMutation`, `useQueryClient` already exist in this file — reuse them; add type imports as needed):

```typescript
import type {
  MatrixConfig,
  MatrixConfigOut,
  MatrixDashboardPrefs,
  MatrixResponse,
  UserSettingOut,
} from './types';

const MATRIX_PREFS_KEY = 'matrix_dashboard';

export function useMatrix(
  scope: string | undefined,
  bootFiles: string[],
  refetchMs: number,
) {
  return useQuery({
    queryKey: ['matrix', scope, [...bootFiles].sort()],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set('scope', scope!);
      for (const bf of bootFiles) params.append('boot_file', bf);
      return (await api.get<MatrixResponse>(`/matrix?${params.toString()}`)).data;
    },
    enabled: Boolean(scope),
    refetchInterval: refetchMs > 0 ? refetchMs : false,
    placeholderData: (prev) => prev, // keep last good data on refetch/scope change
  });
}

export function useMatrixConfig(scope: string | undefined) {
  return useQuery({
    queryKey: ['matrix', 'config', scope],
    queryFn: async () =>
      (await api.get<MatrixConfigOut>(`/matrix/config?scope=${encodeURIComponent(scope!)}`)).data,
    enabled: Boolean(scope),
  });
}

export function useUpsertMatrixConfig(scope: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (config: MatrixConfig) =>
      (await api.put<MatrixConfigOut>(`/matrix/config?scope=${encodeURIComponent(scope)}`, config))
        .data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['matrix', 'config', scope] });
      qc.invalidateQueries({ queryKey: ['matrix', scope] });
    },
  });
}

export function useMatrixPrefs() {
  return useQuery({
    queryKey: ['user', 'settings', MATRIX_PREFS_KEY],
    queryFn: async () => {
      try {
        const res = await api.get<UserSettingOut>(`/me/settings/${MATRIX_PREFS_KEY}`);
        return res.data.value as unknown as MatrixDashboardPrefs;
      } catch (e) {
        // 404 => not set yet; treat as disabled defaults.
        return { enabled: false } as MatrixDashboardPrefs;
      }
    },
  });
}

export function useUpsertMatrixPrefs() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (value: MatrixDashboardPrefs) =>
      (await api.put<UserSettingOut>(`/me/settings/${MATRIX_PREFS_KEY}`, { value })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['user', 'settings', MATRIX_PREFS_KEY] }),
  });
}
```

> Note: if `queries.ts` keeps all imports at the top, move the `import type { ... } from './types'` line up to join the existing type import rather than mid-file. Match the file's existing import style.

- [ ] **Step 2: Typecheck + lint**

Run: `npm run build && npm run lint`
Expected: passes.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/api/queries.ts
git commit -m "feat(web): add matrix + user-settings query hooks"
```

---

## Task 11: `MatrixGrid` component + test

**Files:**
- Create: `apps/web/src/components/MatrixGrid.tsx`
- Test: `apps/web/src/components/MatrixGrid.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/MatrixGrid.test.tsx`:

```typescript
import { ChakraProvider } from '@chakra-ui/react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { system } from '../theme';
import type { MatrixResponse } from '../api/types';
import { MatrixGrid } from './MatrixGrid';

const DATA: MatrixResponse = {
  scope: 'project:kuiper-linux',
  generated_at: new Date().toISOString(),
  row_key: 'hw',
  col_key: 'platform',
  rows: ['ad9081', 'ad9371'],
  cols: ['zcu102', 'zed'],
  boot_files: ['zynqmp-common'],
  stale_after_hours: 48,
  summary: { pass: 1, fail: 1, mixed: 0, error: 0, no_run: 2 },
  unplaced_runs: 0,
  cells: {
    'ad9081|zcu102': {
      status: 'pass', run_id: 'r1', passed: 12, total: 12,
      finished_at: new Date().toISOString(), age_seconds: 120, stale: false,
    },
    'ad9371|zed': {
      status: 'fail', run_id: 'r2', passed: 8, total: 12,
      finished_at: new Date().toISOString(), age_seconds: 99999, stale: true,
    },
  },
};

function renderGrid(data: MatrixResponse = DATA) {
  return render(
    <ChakraProvider value={system}>
      <MatrixGrid data={data} />
    </ChakraProvider>,
  );
}

describe('MatrixGrid', () => {
  it('renders row and column headers', () => {
    renderGrid();
    expect(screen.getByText('ad9081')).toBeInTheDocument();
    expect(screen.getByText('zcu102')).toBeInTheDocument();
  });

  it('renders a PASS cell and a no-run cell', () => {
    renderGrid();
    expect(screen.getByText('PASS')).toBeInTheDocument();
    // ad9081|zed has no cell → no-run marker rendered
    expect(screen.getAllByText('no run').length).toBeGreaterThan(0);
  });

  it('marks a stale cell', () => {
    renderGrid();
    expect(screen.getByText(/stale/i)).toBeInTheDocument();
  });

  it('renders the KPI summary counts', () => {
    renderGrid();
    expect(screen.getByLabelText('pass count')).toHaveTextContent('1');
    expect(screen.getByLabelText('fail count')).toHaveTextContent('1');
    expect(screen.getByLabelText('no run count')).toHaveTextContent('2');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/components/MatrixGrid.test.tsx`
Expected: FAIL — cannot resolve `./MatrixGrid`.

- [ ] **Step 3: Create the component**

Create `apps/web/src/components/MatrixGrid.tsx`:

```typescript
import { Box, Flex, Text } from '@chakra-ui/react';

import type { MatrixCell, MatrixResponse, RunStatus } from '../api/types';

// Bold wall palette (approved mockup). Saturated, glow on fail.
const CELL_STYLE: Record<RunStatus, { bg: string; glow?: string }> = {
  pass: { bg: 'linear-gradient(150deg,#238636,#1a6e2e)' },
  fail: { bg: 'linear-gradient(150deg,#da3633,#a8201d)', glow: '0 0 22px -6px rgba(218,54,51,.7)' },
  mixed: { bg: 'linear-gradient(150deg,#bb8009,#8a5e00)' },
  error: { bg: 'linear-gradient(150deg,#8957e5,#6e40c9)' },
  pending: { bg: '#21262d' },
};

function ageLabel(seconds: number): string {
  if (seconds < 90) return `${seconds}s`;
  if (seconds < 5400) return `${Math.round(seconds / 60)}m`;
  if (seconds < 172800) return `${Math.round(seconds / 3600)}h`;
  return `${Math.round(seconds / 86400)}d`;
}

const ICON: Record<RunStatus, string> = {
  pass: '✓', fail: '✕', mixed: '~', error: '!', pending: '·',
};

function Cell({ cell }: { cell: MatrixCell | undefined }) {
  if (!cell) {
    return (
      <Box
        minH="78px"
        borderRadius="10px"
        border="1px dashed var(--prism-border)"
        bg="var(--prism-bg-surface)"
        color="var(--prism-text-faint)"
        display="flex"
        alignItems="center"
        justifyContent="center"
        fontSize="11px"
      >
        no run
      </Box>
    );
  }
  const style = CELL_STYLE[cell.status];
  return (
    <Box
      minH="78px"
      borderRadius="10px"
      position="relative"
      color="#fff"
      backgroundImage={style.bg}
      boxShadow={style.glow ? `${style.glow}, 0 0 0 1px rgba(255,255,255,.06) inset` : undefined}
      display="flex"
      flexDirection="column"
      alignItems="center"
      justifyContent="center"
      gap="2px"
    >
      {cell.stale && (
        <Box
          position="absolute"
          top="6px"
          left="8px"
          fontSize="8.5px"
          fontWeight="800"
          letterSpacing=".08em"
          bg="#d29922"
          color="#1a1205"
          px="5px"
          borderRadius="4px"
        >
          STALE
        </Box>
      )}
      <Text fontSize="18px" lineHeight="1">{ICON[cell.status]}</Text>
      <Text fontSize="12px" fontWeight="800" letterSpacing=".06em">
        {cell.status.toUpperCase()}
      </Text>
      <Text fontSize="11px" opacity={0.92}>{cell.passed}/{cell.total}</Text>
      <Text position="absolute" bottom="6px" right="8px" fontSize="10px" opacity={0.7}>
        {ageLabel(cell.age_seconds)}
      </Text>
    </Box>
  );
}

function Kpi({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <Flex
      align="center"
      gap="7px"
      bg="var(--prism-bg-surface)"
      border="1px solid var(--prism-border)"
      borderRadius="10px"
      px="12px"
      py="6px"
      fontSize="13px"
      fontWeight="700"
    >
      <Text fontSize="16px" color={color} aria-label={`${label} count`}>{value}</Text>
      <Text color="var(--prism-text-muted)">{label}</Text>
    </Flex>
  );
}

export function MatrixGrid({ data }: { data: MatrixResponse }) {
  const { rows, cols, cells, summary } = data;
  const template = `160px repeat(${cols.length}, 1fr)`;
  return (
    <Box>
      <Flex gap="8px" mb="16px" wrap="wrap">
        <Kpi label="pass" value={summary.pass ?? 0} color="#3fb950" />
        <Kpi label="fail" value={summary.fail ?? 0} color="#ff7b72" />
        <Kpi label="mixed" value={summary.mixed ?? 0} color="#e3b341" />
        <Kpi label="no run" value={summary.no_run ?? 0} color="var(--prism-text-muted)" />
      </Flex>
      <Box display="grid" gridTemplateColumns={template} gap="8px">
        <Box />
        {cols.map((c) => (
          <Text key={c} textAlign="center" fontSize="12px" fontWeight="700"
                color="var(--prism-text-muted)" py="6px">
            {c}
          </Text>
        ))}
        {rows.map((r) => (
          <Box key={r} display="contents">
            <Flex align="center" fontSize="14px" fontWeight="700" color="var(--prism-text)" pr="8px">
              {r}
            </Flex>
            {cols.map((c) => (
              <Cell key={`${r}|${c}`} cell={cells[`${r}|${c}`]} />
            ))}
          </Box>
        ))}
      </Box>
    </Box>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/MatrixGrid.test.tsx`
Expected: PASS. (If the tolerant `14 pass` assertion is awkward, delete that one line — the `aria-label` assertion is the real check.)

- [ ] **Step 5: Lint + typecheck**

Run: `npm run lint && npm run build`
Expected: passes.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/components/MatrixGrid.tsx apps/web/src/components/MatrixGrid.test.tsx
git commit -m "feat(web): add MatrixGrid component"
```

---

## Task 12: `MatrixDashboardPage` + routes

**Files:**
- Create: `apps/web/src/pages/MatrixDashboardPage.tsx`
- Create: `apps/web/src/pages/MatrixDashboardPage.test.tsx`
- Modify: `apps/web/src/App.tsx`

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/pages/MatrixDashboardPage.test.tsx`:

```typescript
import { ChakraProvider } from '@chakra-ui/react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { system } from '../theme';

vi.mock('../components/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock('../api/queries', () => ({
  useMatrix: () => ({
    data: {
      scope: 'project:kuiper-linux', generated_at: new Date().toISOString(),
      row_key: 'hw', col_key: 'platform', rows: ['ad9081'], cols: ['zcu102'],
      boot_files: ['zynqmp-common'], stale_after_hours: 48,
      summary: { pass: 1, fail: 0, mixed: 0, error: 0, no_run: 0 }, unplaced_runs: 0,
      cells: { 'ad9081|zcu102': { status: 'pass', run_id: 'r1', passed: 5, total: 5,
        finished_at: new Date().toISOString(), age_seconds: 60, stale: false } },
    },
    isLoading: false, isError: false,
  }),
  useMatrixConfig: () => ({ data: { scope: 'project:kuiper-linux', config: {
    row_key: 'hw', col_key: 'platform', filter_key: 'boot_file', curated_rows: [],
    curated_cols: [], stale_after_hours: 48, refresh_seconds: 30, rotate_filters: [] } } }),
}));

import { MatrixDashboardPage } from './MatrixDashboardPage';

describe('MatrixDashboardPage', () => {
  it('renders the grid for a project scope', () => {
    render(
      <ChakraProvider value={system}>
        <MemoryRouter initialEntries={['/projects/kuiper-linux/matrix']}>
          <MatrixDashboardPage />
        </MemoryRouter>
      </ChakraProvider>,
    );
    expect(screen.getByText('ad9081')).toBeInTheDocument();
    expect(screen.getByText('PASS')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/pages/MatrixDashboardPage.test.tsx`
Expected: FAIL — cannot resolve `./MatrixDashboardPage`.

- [ ] **Step 3: Create the page**

Create `apps/web/src/pages/MatrixDashboardPage.tsx`:

```typescript
import { Box, Button, Flex, Heading, Text } from '@chakra-ui/react';
import { useState } from 'react';
import { useParams } from 'react-router-dom';

import { useMatrix, useMatrixConfig } from '../api/queries';
import { AppShell } from '../components/AppShell';
import { MatrixGrid } from '../components/MatrixGrid';

export function MatrixDashboardPage() {
  const { slug } = useParams();
  const scope = slug ? `project:${slug}` : 'global';
  const config = useMatrixConfig(scope);
  const refreshMs = (config.data?.config.refresh_seconds ?? 30) * 1000;

  const [bootFiles, setBootFiles] = useState<string[]>([]);
  const q = useMatrix(scope, bootFiles, refreshMs);

  const toggleBoot = (bf: string) =>
    setBootFiles((cur) => (cur.includes(bf) ? cur.filter((x) => x !== bf) : [...cur, bf]));

  return (
    <AppShell>
      <Box p={8}>
        <Flex justify="space-between" align="center" mb={2}>
          <Heading size="xl">Matrix — {scope === 'global' ? 'All releases' : slug}</Heading>
          {q.isFetching && <Text fontSize="sm" color="var(--prism-text-muted)">refreshing…</Text>}
        </Flex>
        {q.isError && !q.data && (
          <Text color="red.400">Failed to load matrix.</Text>
        )}
        {q.data && (
          <>
            {q.data.boot_files.length > 0 && (
              <Flex gap={2} mb={4} wrap="wrap" align="center">
                <Text fontSize="sm" color="var(--prism-text-muted)">boot file:</Text>
                {q.data.boot_files.map((bf) => (
                  <Button
                    key={bf}
                    size="xs"
                    variant={bootFiles.includes(bf) ? 'solid' : 'outline'}
                    colorPalette="blue"
                    onClick={() => toggleBoot(bf)}
                  >
                    {bf}
                  </Button>
                ))}
                {bootFiles.length > 0 && (
                  <Button size="xs" variant="ghost" onClick={() => setBootFiles([])}>
                    clear
                  </Button>
                )}
              </Flex>
            )}
            {q.data.unplaced_runs > 0 && (
              <Text fontSize="xs" color="var(--prism-text-faint)" mb={2}>
                {q.data.unplaced_runs} run(s) missing hw/platform tags are not shown.
              </Text>
            )}
            <MatrixGrid data={q.data} />
          </>
        )}
      </Box>
    </AppShell>
  );
}
```

- [ ] **Step 4: Add the routes**

In `apps/web/src/App.tsx`, add the import:

```typescript
import { MatrixDashboardPage } from './pages/MatrixDashboardPage';
```

and add inside `<Routes>` (mirror the existing `ProtectedRoute` wrapping style):

```typescript
<Route path="/matrix" element={<ProtectedRoute><MatrixDashboardPage /></ProtectedRoute>} />
<Route path="/projects/:slug/matrix" element={<ProtectedRoute><MatrixDashboardPage /></ProtectedRoute>} />
```

> Place the `/projects/:slug/matrix` route so it doesn't shadow `/projects/:slug` — React Router v6 matches the more specific path regardless of order, but keep it adjacent to the other project routes for readability.

- [ ] **Step 5: Run test to verify it passes**

Run: `npx vitest run src/pages/MatrixDashboardPage.test.tsx`
Expected: PASS

- [ ] **Step 6: Lint + typecheck**

Run: `npm run lint && npm run build`
Expected: passes.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/pages/MatrixDashboardPage.tsx apps/web/src/pages/MatrixDashboardPage.test.tsx apps/web/src/App.tsx
git commit -m "feat(web): add MatrixDashboardPage and routes"
```

---

## Task 13: `MatrixKioskPage` + route (fullscreen, auto-rotate)

**Files:**
- Create: `apps/web/src/pages/MatrixKioskPage.tsx`
- Modify: `apps/web/src/App.tsx`

- [ ] **Step 1: Create the kiosk page**

Create `apps/web/src/pages/MatrixKioskPage.tsx`:

```typescript
import { Box, Flex, Text } from '@chakra-ui/react';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { useMatrix, useMatrixConfig } from '../api/queries';
import { MatrixGrid } from '../components/MatrixGrid';

export function MatrixKioskPage() {
  const [params] = useSearchParams();
  const scope = params.get('scope') ?? 'global';
  const config = useMatrixConfig(scope);
  const cfg = config.data?.config;
  const refreshMs = (cfg?.refresh_seconds ?? 30) * 1000;
  const rotateFilters = cfg?.rotate_filters ?? [];

  // Auto-rotate through configured boot-file filters (always on in kiosk).
  const [rotIdx, setRotIdx] = useState(0);
  useEffect(() => {
    if (rotateFilters.length < 2) return;
    const t = setInterval(() => setRotIdx((i) => (i + 1) % rotateFilters.length), refreshMs);
    return () => clearInterval(t);
  }, [rotateFilters.length, refreshMs]);

  const activeBoot = rotateFilters.length > 0 ? [rotateFilters[rotIdx % rotateFilters.length]] : [];
  const q = useMatrix(scope, activeBoot, refreshMs);

  return (
    <Box minH="100vh" bg="var(--prism-bg-canvas)" p={6}>
      <Flex justify="space-between" align="baseline" mb={4}>
        <Text fontSize="2xl" fontWeight="800" color="var(--prism-text)">
          Kuiper Linux — {scope === 'global' ? 'All releases' : scope.replace('project:', '')}
        </Text>
        <Text fontSize="sm" color="var(--prism-text-muted)">
          {activeBoot.length > 0 ? `showing: ${activeBoot[0]} · ` : ''}
          {q.isFetching ? 'refreshing…' : 'live'}
        </Text>
      </Flex>
      {q.data ? (
        <MatrixGrid data={q.data} />
      ) : (
        <Text color="var(--prism-text-muted)">Loading…</Text>
      )}
    </Box>
  );
}
```

- [ ] **Step 2: Add the route (still auth-gated, no AppShell)**

In `apps/web/src/App.tsx`, add the import:

```typescript
import { MatrixKioskPage } from './pages/MatrixKioskPage';
```

and the route (wrapped in `ProtectedRoute` for auth, but NOT `AppShell` — the page renders its own full-bleed layout):

```typescript
<Route path="/kiosk/matrix" element={<ProtectedRoute><MatrixKioskPage /></ProtectedRoute>} />
```

- [ ] **Step 3: Typecheck + lint**

Run: `npm run build && npm run lint`
Expected: passes.

- [ ] **Step 4: Manual smoke (optional, if stack is up)**

Open `http://localhost:8180/kiosk/matrix?scope=global` — confirm no sidebar/topbar, grid fills the page.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/pages/MatrixKioskPage.tsx apps/web/src/App.tsx
git commit -m "feat(web): add fullscreen matrix kiosk route with auto-rotate"
```

---

## Task 14: Enable toggle + conditional nav entry

**Files:**
- Create: `apps/web/src/pages/MatrixSettingsCard.tsx`
- Modify: `apps/web/src/pages/TokensPage.tsx` (mount the card under the existing settings-style page)
- Modify: `apps/web/src/components/Sidebar.tsx` (conditional Matrix nav)

- [ ] **Step 1: Create the settings card**

Create `apps/web/src/pages/MatrixSettingsCard.tsx`:

```typescript
import { Box, Button, Heading, Stack, Text } from '@chakra-ui/react';

import { useMatrixPrefs, useUpsertMatrixPrefs } from '../api/queries';

export function MatrixSettingsCard() {
  const prefs = useMatrixPrefs();
  const upsert = useUpsertMatrixPrefs();
  const enabled = prefs.data?.enabled ?? false;

  const toggle = () =>
    upsert.mutate({ ...(prefs.data ?? { enabled: false }), enabled: !enabled });

  return (
    <Box mt={10} maxW="900px">
      <Heading size="lg" mb={2}>Matrix dashboard</Heading>
      <Text color="var(--prism-text-subtle)" mb={4} fontSize="sm">
        A glanceable coverage wall of board/platform status. Enabling it adds a{' '}
        <strong>Matrix</strong> entry to your navigation.
      </Text>
      <Stack direction="row" align="center" gap={3}>
        <Button
          colorPalette={enabled ? 'red' : 'blue'}
          onClick={toggle}
          loading={upsert.isPending}
        >
          {enabled ? 'Disable' : 'Enable'} matrix dashboard
        </Button>
        <Text fontSize="sm" color="var(--prism-text-muted)">
          Currently {enabled ? 'enabled' : 'disabled'}.
        </Text>
      </Stack>
    </Box>
  );
}
```

- [ ] **Step 2: Mount the card on the Tokens page**

In `apps/web/src/pages/TokensPage.tsx`, add the import:

```typescript
import { MatrixSettingsCard } from './MatrixSettingsCard';
```

and render `<MatrixSettingsCard />` just before the closing `</Box>`/`</AppShell>` of the page's main content (after the tokens table). Example placement:

```typescript
        {/* ...existing tokens table... */}
        <MatrixSettingsCard />
      </Box>
    </AppShell>
```

- [ ] **Step 3: Conditional nav entry in Sidebar**

In `apps/web/src/components/Sidebar.tsx`, import the prefs hook:

```typescript
import { useMatrixPrefs } from '../api/queries';
```

Inside the component body, read the prefs and build the nav list conditionally. Find the existing line that assembles `navItems` (`const navItems = user?.is_admin ? [...BASE_NAV, ADMIN_NAV] : BASE_NAV;`) and replace it with:

```typescript
const matrixPrefs = useMatrixPrefs();
const matrixEnabled = matrixPrefs.data?.enabled ?? false;
const MATRIX_NAV = { to: '/matrix', label: 'Matrix', short: 'M', end: true };

let navItems = [...BASE_NAV];
if (matrixEnabled) {
  // Insert Matrix before Tokens for grouping.
  const tokensIdx = navItems.findIndex((n) => n.to === '/tokens');
  if (tokensIdx >= 0) navItems.splice(tokensIdx, 0, MATRIX_NAV);
  else navItems.push(MATRIX_NAV);
}
if (user?.is_admin) navItems.push(ADMIN_NAV);
```

> Confirm `BASE_NAV`/`ADMIN_NAV`/`user` are in scope exactly as named in the current Sidebar. Keep the `{ to, label, short, end }` shape consistent with existing entries.

- [ ] **Step 4: Typecheck + lint + existing tests**

Run: `npm run build && npm run lint && npx vitest run`
Expected: passes (no existing test asserts the exact nav set; if one does, update it to account for the conditional Matrix entry).

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/pages/MatrixSettingsCard.tsx apps/web/src/pages/TokensPage.tsx apps/web/src/components/Sidebar.tsx
git commit -m "feat(web): per-user matrix enable toggle and conditional nav"
```

---

## Task 15: Minimal admin matrix-config form

**Files:**
- Modify: `apps/web/src/pages/AdminPage.tsx`

- [ ] **Step 1: Add a Matrix config section to AdminPage**

In `apps/web/src/pages/AdminPage.tsx`, add imports:

```typescript
import { useState } from 'react';
import { useMatrixConfig, useUpsertMatrixConfig } from '../api/queries';
import type { MatrixConfig } from '../api/types';
```

Add a `MatrixConfigTab` component in the same file (mirroring the existing tab component style in this file):

```typescript
export function MatrixConfigTab() {
  const [scope, setScope] = useState('global');
  const cfgQ = useMatrixConfig(scope);
  const upsert = useUpsertMatrixConfig(scope);
  const cfg = cfgQ.data?.config;

  const [stale, setStale] = useState('');
  const [refresh, setRefresh] = useState('');
  const [rows, setRows] = useState('');
  const [cols, setCols] = useState('');
  const [rotate, setRotate] = useState('');

  const save = () => {
    if (!cfg) return;
    const next: MatrixConfig = {
      ...cfg,
      stale_after_hours: stale ? Number(stale) : cfg.stale_after_hours,
      refresh_seconds: refresh ? Number(refresh) : cfg.refresh_seconds,
      curated_rows: rows ? rows.split(',').map((s) => s.trim()).filter(Boolean) : cfg.curated_rows,
      curated_cols: cols ? cols.split(',').map((s) => s.trim()).filter(Boolean) : cfg.curated_cols,
      rotate_filters: rotate
        ? rotate.split(',').map((s) => s.trim()).filter(Boolean)
        : cfg.rotate_filters,
    };
    upsert.mutate(next);
  };

  return (
    <Box maxW="700px">
      <Heading size="md" mb={3}>Matrix dashboard config</Heading>
      <Stack gap={3}>
        <Input placeholder="scope (global or project:slug)" value={scope}
               onChange={(e) => setScope(e.target.value)} aria-label="scope" />
        <Text fontSize="sm" color="var(--prism-text-muted)">
          Current: stale {cfg?.stale_after_hours}h · refresh {cfg?.refresh_seconds}s ·
          curated rows [{cfg?.curated_rows.join(', ')}] · cols [{cfg?.curated_cols.join(', ')}] ·
          rotate [{cfg?.rotate_filters.join(', ')}]
        </Text>
        <Input placeholder="stale_after_hours" type="number" value={stale}
               onChange={(e) => setStale(e.target.value)} aria-label="stale hours" />
        <Input placeholder="refresh_seconds" type="number" value={refresh}
               onChange={(e) => setRefresh(e.target.value)} aria-label="refresh seconds" />
        <Input placeholder="curated_rows (comma list)" value={rows}
               onChange={(e) => setRows(e.target.value)} aria-label="curated rows" />
        <Input placeholder="curated_cols (comma list)" value={cols}
               onChange={(e) => setCols(e.target.value)} aria-label="curated cols" />
        <Input placeholder="rotate_filters (comma list)" value={rotate}
               onChange={(e) => setRotate(e.target.value)} aria-label="rotate filters" />
        <Button colorPalette="blue" onClick={save} loading={upsert.isPending} alignSelf="start">
          Save matrix config
        </Button>
        {upsert.isError && <Text color="red.400" fontSize="sm">Save failed (admin only).</Text>}
      </Stack>
    </Box>
  );
}
```

Then render `<MatrixConfigTab />` within AdminPage's existing tab/section layout (add a tab labeled "Matrix" mirroring how other tabs like Projects/Accounts are registered in this file). Ensure `Box`, `Heading`, `Stack`, `Input`, `Button`, `Text` are imported (most already are in AdminPage).

> Confirm AdminPage's tab mechanism (it may use Chakra `Tabs.Root` or a custom switch). Add the Matrix tab the same way the existing tabs are added. If AdminPage is a flat page rather than tabbed, append `<MatrixConfigTab />` as a new section.

- [ ] **Step 2: Typecheck + lint**

Run: `npm run build && npm run lint`
Expected: passes.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/pages/AdminPage.tsx
git commit -m "feat(web): minimal admin matrix-config form"
```

---

## Task 16: Seed demo data

**Files:**
- Modify: `apps/api/scripts/seed_demo.py`

- [ ] **Step 1: Inspect the current seeding**

Read `apps/api/scripts/seed_demo.py` to find where runs are created and how tags (if any) are attached. Identify the helper that creates a run.

- [ ] **Step 2: Add matrix tags to seeded runs**

Add a small matrix of seeded runs carrying `hw`, `platform`, `boot_file`, and (for some) `kuiper-linux-release` tags. Insert near the existing run-creation code, using whatever run/tag creation helper the script already uses. Concrete data to seed (adapt to the script's existing API for creating a run + tag):

```python
MATRIX_SEED = [
    # (hw, platform, boot_file, status, release)
    ("ad9081", "zcu102", "zynqmp-common", "pass", "2024_R2"),
    ("ad9081", "zc706", "zynq-common", "fail", "2024_R2"),
    ("adrv9009", "zcu102", "zynqmp-common", "pass", "2024_R2"),
    ("adrv9009", "zed", "zynq-common", "mixed", "2024_R2"),
    ("ad9371", "zed", "zynq-common", "pass", None),
    ("ad9371", "zc706", "zynq-common", "fail", None),
    ("adrv9026", "a10soc", "socfpga_arria10_common", "pass", "2024_R2"),
]
# For each tuple, create a TestRun in the kuiper-linux project with the given status,
# a finished_at of "now", one TestSuite with representative pass/fail counts, and
# RunTag rows: hw=<hw>, platform=<platform>, boot_file=<boot_file>, and
# kuiper-linux-release=<release> when release is not None.
```

> Match the script's existing patterns exactly (it may go through the HTTP API or directly through repos). The key requirement: after seeding, `GET /api/v1/matrix?scope=project:kuiper-linux` returns multiple rows/cols, and `scope=global` returns the release-tagged subset.

- [ ] **Step 3: Run the seed against a dev stack**

Run (with the stack up): `uv run python scripts/seed_demo.py`
Expected: completes without error; the kuiper-linux project has the matrix runs.

- [ ] **Step 4: Lint**

Run: `uv run ruff check .`
Expected: no errors. (seed_demo may be excluded from mypy; match existing config.)

- [ ] **Step 5: Commit**

```bash
git add apps/api/scripts/seed_demo.py
git commit -m "chore(api): seed matrix dashboard demo data"
```

---

## Task 17: E2E test

**Files:**
- Create: `apps/web/e2e/matrix.spec.ts`

- [ ] **Step 1: Write the e2e test**

Create `apps/web/e2e/matrix.spec.ts` (mirror `e2e/compare.spec.ts` login + axe helpers):

```typescript
import { expect, test } from '@playwright/test';
import { expectNoSeriousAxeViolations } from './helpers/axe';

const EMAIL = process.env.PLAYWRIGHT_ADMIN_EMAIL ?? 'admin@example.com';
const PASSWORD = process.env.PLAYWRIGHT_ADMIN_PASSWORD ?? 'change-me-in-prod';

async function login(page: import('@playwright/test').Page) {
  await page.goto('/login');
  await page.fill('input[type=email]', EMAIL);
  await page.fill('input[type=password]', PASSWORD);
  await page.click('button[type=submit]');
  await page.waitForURL((url) => url.pathname === '/');
}

test('enable matrix dashboard, view grid, and check kiosk', async ({ page }) => {
  await login(page);

  // Enable via the settings card on the Tokens page.
  await page.goto('/tokens');
  await page.click('button:has-text("Enable matrix dashboard")');
  await expect(page.getByText('Currently enabled.')).toBeVisible();

  // Nav entry now appears; open the matrix.
  await page.click('a[href="/matrix"]');
  await page.waitForURL('/matrix');
  await expect(page.getByRole('heading', { name: /^matrix/i })).toBeVisible();
  await expectNoSeriousAxeViolations(page);

  // Kiosk route renders without the sidebar nav.
  await page.goto('/kiosk/matrix?scope=global');
  await expect(page.getByText(/Kuiper Linux/i)).toBeVisible();
  await expect(page.locator('a[href="/tokens"]')).toHaveCount(0); // no sidebar
  await expectNoSeriousAxeViolations(page);
});
```

- [ ] **Step 2: Run the e2e test**

Run (stack up + seeded): `npm run e2e -- matrix.spec.ts`
Expected: PASS, no serious/critical axe violations. If color-contrast on the bold cells trips axe, verify the disabled-rules config in `e2e/helpers/axe.ts` (color-contrast is already disabled there) — but still eyeball contrast manually.

- [ ] **Step 3: Commit**

```bash
git add apps/web/e2e/matrix.spec.ts
git commit -m "test(web): e2e for matrix dashboard enable + kiosk"
```

---

## Task 18: Documentation

**Files:**
- Create: `docs/source/how-to/matrix-dashboard.md`
- Modify: the docs toctree/index that lists how-to pages (find the how-to index under `docs/source/how-to/`).

- [ ] **Step 1: Write the how-to**

Create `docs/source/how-to/matrix-dashboard.md` covering:
- What the matrix dashboard is and the tag convention (`hw`, `platform`, `boot_file`, `kuiper-linux-release`).
- How to enable it per-user (Tokens/settings page → Enable matrix dashboard).
- Per-project (`/projects/<slug>/matrix`) vs global superset (`/matrix` or scope `global`).
- Kiosk usage on a TV: open `/kiosk/matrix?scope=global` in the TV browser; the session must be logged in; auto-refresh + rotation are driven by admin config.
- Admin config: curated rows/cols, `stale_after_hours`, `refresh_seconds`, `rotate_filters` via the Admin page.

```markdown
# Matrix dashboard

The matrix dashboard is a glanceable coverage wall: rows are ADI hardware (`hw`
tag), columns are carrier/dev platforms (`platform` tag), and each cell shows the
latest test run's status for that combination. Filter the wall by the boot image
used to test the system (`boot_file` tag).

## Tagging your runs

Cells are built from run tags. When uploading a run, set:

- `hw` — the ADI hardware (e.g. `ad9081`)
- `platform` — the carrier / dev platform (e.g. `zcu102`)
- `boot_file` — the SD-card image used (e.g. `zynqmp-common`)
- `kuiper-linux-release` — (optional) the release (e.g. `2024_R2`); runs with this
  tag appear in the global superset view across all projects.

## Enabling the dashboard

Open the settings area (Tokens page) and click **Enable matrix dashboard**. A
**Matrix** entry appears in your navigation.

## Scopes

- Per project: `/projects/<slug>/matrix` — only that project's boards.
- Global superset: `/matrix` (scope `global`) — every run tagged
  `kuiper-linux-release`, unioned across projects.

## Kiosk / TV mode

Open `/kiosk/matrix?scope=global` in the TV's browser. The page is chrome-less and
auto-refreshes. The browser must hold a logged-in Prism session. Admins can
configure rotation through boot-file filters so one TV cycles several views.

## Admin configuration

On the Admin page, the **Matrix** section configures, per scope:

- `curated_rows` / `curated_cols` — pin boards/platforms that should appear even
  with zero runs (surfacing true coverage gaps).
- `stale_after_hours` — when a cell is flagged stale (default 48).
- `refresh_seconds` — auto-refresh cadence (default 30).
- `rotate_filters` — ordered boot-file values the kiosk cycles through.
```

- [ ] **Step 2: Add to the how-to index**

Add `matrix-dashboard` to the how-to toctree (match the existing entries' format in the how-to index file).

- [ ] **Step 3: Build docs (if tooling available)**

Run: `make docs` (or the project's docs build) and confirm no warnings about the new page.

- [ ] **Step 4: Commit**

```bash
git add docs/source/how-to/matrix-dashboard.md docs/source/how-to/
git commit -m "docs: matrix dashboard how-to"
```

---

## Final verification

- [ ] **Backend:** `cd apps/api && uv run pytest && uv run ruff check . && uv run mypy src` — all green.
- [ ] **Frontend:** `cd apps/web && npx vitest run && npm run lint && npm run build` — all green.
- [ ] **E2E (stack up + seeded):** `npm run e2e -- matrix.spec.ts` — passes, no serious axe violations.
- [ ] **Manual:** enable the dashboard, view `/matrix` and `/projects/kuiper-linux/matrix`, toggle a boot-file filter, open `/kiosk/matrix?scope=global` on a second screen, set `stale_after_hours` low in admin and confirm a cell flips to stale.
```
