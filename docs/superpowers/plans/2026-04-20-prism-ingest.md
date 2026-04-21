# Prism — Ingest Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a working ingest pipeline — `POST /api/v1/runs` accepts a JUnit XML + optional archive of measurement artifacts, a Celery worker parses them into Run/Suite/Case/Artifact rows in Postgres and stores originals in MinIO. Also fold in the five Important fixups the Plan 1 final reviewer flagged.

**Architecture:** FastAPI endpoint creates a `TestRun(status=pending)`, writes the uploaded archive+JUnit to a content-addressed location in MinIO, enqueues `ingest_run` on Redis. Celery worker pulls the task, parses JUnit (via `junitparser`), extracts the artifact archive to a temp dir, identifies each file's `kind` via extension + magic bytes, hashes + uploads each file (deduplicated), and links it to the owning `Suite`/`Case` via the filename convention `{suite}__{case}__{label}.{ext}`. Worker then sets `TestRun.status` to `pass`/`fail`/`mixed`/`error` based on the JUnit results.

**Tech Stack:** Adds `celery[redis]`, `boto3`, `junitparser`, `python-magic`, `h5py` (all already in `pyproject.toml` from Plan 1). Moto for S3-in-memory tests; testcontainers or a direct redis fixture for Celery integration tests.

---

## Conventions

- All paths relative to repo root `/home/tcollins/dev/prism`.
- Bash commands assume `cd /home/tcollins/dev/prism/apps/api` for pytest / alembic.
- Each task ends with a commit. Commit messages follow Conventional Commits.
- TDD: write the failing test first, run it (FAIL), implement, run (PASS), commit.
- The bash tool's persistent cwd may be pinned to a stub directory; use absolute paths or explicit `cd` in every shell invocation.

## What the plan 1 reviewer flagged that we're addressing here

- **I1** — `cookie_secure` configurable via `Settings` (Task 0.1)
- **I2** — `delete_user` rejects self-delete and last-user deletion + returns 404 on unknown (Task 0.2)
- **I3** — delete dead `db.get_session` (Task 0.3)
- **I4** — `logout` delete-cookie preserves `samesite`/`secure` attrs (Task 0.1)
- **Security (S5)** — `jwt_secret` rejects placeholder / short values (Task 0.4)
- **Entrypoint swallowed errors** — remove `|| true` from `docker-entrypoint.sh` (Task 0.5)

Plan-3 items (frontend) are **out of scope** for Plan 2: I5 (AuthProvider error discrimination), S7 (split `AuthContext`), web/Dockerfile `npm ci` (S2). Those land in Plan 3's security sweep.

---

## Phase 0: Plan-1 fixups

### Task 0.1: Cookie hardening (I1 + I4)

**Files:**
- Modify: `apps/api/src/prism_api/config.py` (add `cookie_secure: bool = False`, `cookie_samesite: Literal["lax","strict","none"] = "lax"`)
- Modify: `apps/api/src/prism_api/routers/auth.py` (use settings on login + logout)
- Modify: `apps/api/tests/conftest.py` (pass new fields in test Settings construction)
- Test: `apps/api/tests/test_auth_router.py` (extend)

- [ ] **Step 1: Add failing test**

Append to `apps/api/tests/test_auth_router.py`:
```python
def test_login_cookie_attributes(client, seed_admin):
    r = client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    assert r.status_code == 200
    set_cookie = r.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie.lower() or "samesite=lax" in set_cookie.lower()


def test_logout_cookie_attributes(client, seed_admin):
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    r = client.post("/api/v1/auth/logout")
    set_cookie = r.headers.get("set-cookie", "")
    # Deletion cookie should preserve samesite=lax for browser to accept
    assert "samesite=lax" in set_cookie.lower()
```

- [ ] **Step 2: Run test (FAIL — `SameSite` not set or wrong on delete)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_auth_router.py -v -k cookie_attributes
```

- [ ] **Step 3: Update Settings**

Replace `apps/api/src/prism_api/config.py`:
```python
"""App configuration via pydantic-settings."""
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PRISM_", case_sensitive=False)

    database_url: str
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str
    redis_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_ttl_minutes: int = Field(default=60 * 24)
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    admin_email: str | None = None
    admin_password: str | None = None

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_not_placeholder(cls, v: str) -> str:
        if len(v) < 16:
            raise ValueError("PRISM_JWT_SECRET must be at least 16 characters")
        if v in {"replace-with-a-long-random-string", "change-me-in-prod"}:
            raise ValueError("PRISM_JWT_SECRET appears to be an example placeholder; set a real secret")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

- [ ] **Step 4: Update auth router**

Replace the cookie-setting block in `apps/api/src/prism_api/routers/auth.py` — both login's `set_cookie` and logout's `delete_cookie` read from settings:

```python
# in login():
response.set_cookie(
    key=SESSION_COOKIE,
    value=token,
    httponly=True,
    samesite=settings.cookie_samesite,
    secure=settings.cookie_secure,
    max_age=settings.jwt_ttl_minutes * 60,
    path="/",
)

# in logout(): rewrite signature to accept settings
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, settings: Settings = Depends(get_settings_dep)) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
    )
```

- [ ] **Step 5: Update conftest fixture**

In `apps/api/tests/conftest.py` `settings` fixture, ensure `jwt_secret="testsecretlongenough"` (≥16 chars) so the new validator passes.

- [ ] **Step 6: Run tests (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest -v
```
Expected: 34 passing (32 original + 2 new).

- [ ] **Step 7: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(api): configurable cookie_secure/samesite, preserved on logout (I1+I4)"
```

---

### Task 0.2: delete_user guards (I2)

**Files:**
- Modify: `apps/api/src/prism_api/repos/users.py` (`delete` returns bool)
- Modify: `apps/api/src/prism_api/routers/users.py`
- Test: `apps/api/tests/test_users_router.py` (extend)

- [ ] **Step 1: Add failing tests**

Append to `apps/api/tests/test_users_router.py`:
```python
def test_cannot_delete_self(client, seed_admin):
    _login(client)
    me = client.get("/api/v1/auth/me").json()
    r = client.delete(f"/api/v1/users/{me['id']}")
    assert r.status_code == 400
    assert "self" in r.json()["detail"].lower()


def test_cannot_delete_last_user(client, seed_admin):
    _login(client)
    me = client.get("/api/v1/auth/me").json()
    # With only the admin user, delete of another (nonexistent) is still possible
    # but delete of last remaining user should be blocked even via someone else's id
    # so: create a second user, delete the other one, then the only remaining must refuse
    second = client.post("/api/v1/users", json={"email": "other@x.com", "password": "longpw!!"}).json()
    client.delete(f"/api/v1/users/{me['id']}")  # self-delete is blocked anyway; irrelevant here
    # Log in as the second user
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"email": "other@x.com", "password": "longpw!!"})
    # Try to delete admin (the only other user) — should succeed, leaving just `second`
    r = client.delete(f"/api/v1/users/{me['id']}")
    assert r.status_code == 204
    # Now `second` is the only user; trying to delete itself is blocked (self-guard wins)
    r2 = client.delete(f"/api/v1/users/{second['id']}")
    assert r2.status_code == 400


def test_delete_unknown_user_404(client, seed_admin):
    _login(client)
    r = client.delete("/api/v1/users/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
```

- [ ] **Step 2: Update `UserRepo.delete` to return bool**

`apps/api/src/prism_api/repos/users.py` — change the method:
```python
def delete(self, user_id: str) -> bool:
    user = self._session.get(User, user_id)
    if user is None:
        return False
    self._session.delete(user)
    return True
```

- [ ] **Step 3: Update users router**

`apps/api/src/prism_api/routers/users.py`:
```python
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    current: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> Response:
    repo = UserRepo(session)
    if current.id == user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot delete yourself")
    # Must have at least one user remaining
    total = len(repo.list_all())
    if total <= 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot delete the last remaining user")
    if not repo.delete(user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Run tests (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_users_router.py -v
```
Expected: 7 passing.

- [ ] **Step 5: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(api): delete_user guards against self/last-user and returns 404 (I2)"
```

---

### Task 0.3: Delete dead `db.get_session` (I3)

- [ ] **Step 1: Remove `get_session` from `apps/api/src/prism_api/db.py`**

Delete the `get_session` function (the bottom of the file). Leave `build_engine`, `build_session_factory`, `_factory`, and `session_scope`. `deps.session_dep` already re-implements the dependency pattern, so nothing references the deleted function.

- [ ] **Step 2: Verify no references**

```bash
cd /home/tcollins/dev/prism/apps/api && grep -rn "get_session" src tests
```
Expected: no output.

- [ ] **Step 3: Run tests**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest -v
```
Expected: all passing.

- [ ] **Step 4: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "refactor(api): drop dead db.get_session (dup of deps.session_dep) (I3)"
```

---

### Task 0.4: Stop swallowing errors in entrypoint

- [ ] **Step 1: Edit `apps/api/docker-entrypoint.sh`**

Replace:
```sh
#!/bin/sh
set -e
alembic upgrade head
python -m prism_api.cli bootstrap-admin
exec "$@"
```

(remove `|| true`; the CLI is safely idempotent and a real failure should stop the container.)

- [ ] **Step 2: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/docker-entrypoint.sh && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "fix(api): entrypoint no longer swallows bootstrap errors"
```

---

### Task 0.5: Update `.env.example` JWT secret so Settings validator is obvious

- [ ] **Step 1: Replace the placeholder JWT secret**

`deploy/.env.example` — change the `JWT_SECRET` line to a real-but-obviously-dev secret:
```
JWT_SECRET=dev-only-replace-with-32-plus-random-chars-please
```

Regenerate your local `.env` from it: `cp deploy/.env.example deploy/.env`.

- [ ] **Step 2: Commit**

```bash
cd /home/tcollins/dev/prism && git add deploy/.env.example && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "chore(deploy): switch example JWT secret off validator blacklist"
```

---

## Phase 1: Ingest data models

### Task 1.1: Model files

**Files:**
- Create: `apps/api/src/prism_api/models/run.py` (TestRun, RunTag)
- Create: `apps/api/src/prism_api/models/suite.py` (TestSuite, TestCase)
- Create: `apps/api/src/prism_api/models/artifact.py` (Artifact, DerivedArtifact)
- Modify: `apps/api/src/prism_api/models/__init__.py`
- Test: `apps/api/tests/test_models_ingest.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_models_ingest.py`:
```python
"""Smoke tests for ingest-pipeline models against in-memory SQLite."""
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from prism_api.models import Base
from prism_api.models.artifact import Artifact, ArtifactKind, DerivedArtifact, DerivedKind
from prism_api.models.project import Project
from prism_api.models.run import RunStatus, RunTag, TestRun
from prism_api.models.suite import CaseStatus, TestCase, TestSuite


def test_full_run_tree_round_trip() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        project = Project(slug="a", name="A")
        s.add(project)
        s.flush()

        run = TestRun(
            project_id=project.id,
            name="nightly-42",
            status=RunStatus.PENDING,
            started_at=datetime.now(UTC),
        )
        s.add(run)
        s.flush()

        s.add_all([
            RunTag(run_id=run.id, key="branch", value="main"),
            RunTag(run_id=run.id, key="sha", value="abc123"),
        ])

        suite = TestSuite(run_id=run.id, name="dsp", pass_count=1, fail_count=0, error_count=0, skip_count=0, duration_ms=42)
        s.add(suite)
        s.flush()

        case = TestCase(suite_id=suite.id, classname="codec", name="sine_sweep", status=CaseStatus.PASS, duration_ms=10)
        s.add(case)
        s.flush()

        artifact = Artifact(
            owner_type="case",
            owner_id=case.id,
            kind=ArtifactKind.WAVEFORM_CSV,
            filename="sine.csv",
            size_bytes=1024,
            content_hash="deadbeef" * 8,
            storage_key="raw/de/deadbeef" + "deadbeef" * 7,
            metadata_json={"sample_rate": 48000},
        )
        s.add(artifact)
        s.flush()

        derived = DerivedArtifact(
            source_artifact_id=artifact.id,
            kind=DerivedKind.FFT,
            storage_key="derived/fft/x.npy",
            params_hash="f" * 32,
        )
        s.add(derived)
        s.commit()

        assert run.id and suite.id and case.id and artifact.id and derived.id
        tags = s.query(RunTag).filter(RunTag.run_id == run.id).all()
        assert {t.key for t in tags} == {"branch", "sha"}
```

- [ ] **Step 2: Run test (FAIL — ModuleNotFoundError on run/suite/artifact)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_models_ingest.py -v
```

- [ ] **Step 3: Implement models**

`apps/api/src/prism_api/models/run.py`:
```python
"""Run + run-tag models."""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from prism_api.models.base import Base, TimestampMixin


class RunStatus(str, enum.Enum):
    PENDING = "pending"
    PASS = "pass"
    FAIL = "fail"
    MIXED = "mixed"
    ERROR = "error"


class TestRun(Base, TimestampMixin):
    __tablename__ = "test_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus, native_enum=False), nullable=False, default=RunStatus.PENDING)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    junit_artifact_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class RunTag(Base):
    __tablename__ = "run_tags"

    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("test_runs.id", ondelete="CASCADE"), primary_key=True)
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(500), nullable=False)

    __table_args__ = (Index("ix_run_tags_kv", "key", "value"),)
```

`apps/api/src/prism_api/models/suite.py`:
```python
"""Suite + case models."""
import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from prism_api.models.base import Base, TimestampMixin


class CaseStatus(str, enum.Enum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    SKIP = "skip"


class TestSuite(Base, TimestampMixin):
    __tablename__ = "test_suites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    pass_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skip_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class TestCase(Base, TimestampMixin):
    __tablename__ = "test_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    suite_id: Mapped[str] = mapped_column(String(36), ForeignKey("test_suites.id", ondelete="CASCADE"), nullable=False, index=True)
    classname: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[CaseStatus] = mapped_column(Enum(CaseStatus, native_enum=False), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_trace: Mapped[str | None] = mapped_column(Text, nullable=True)
```

`apps/api/src/prism_api/models/artifact.py`:
```python
"""Artifact + derived-artifact models."""
import enum
import uuid
from typing import Any

from sqlalchemy import BigInteger, Enum, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from prism_api.models.base import Base, TimestampMixin


class ArtifactKind(str, enum.Enum):
    JUNIT_XML = "junit_xml"
    WAVEFORM_CSV = "waveform_csv"
    WAVEFORM_HDF5 = "waveform_hdf5"
    WAVEFORM_NPY = "waveform_npy"
    WAV_AUDIO = "wav_audio"
    IMAGE_PNG = "image_png"
    LOG_TEXT = "log_text"
    OTHER_BINARY = "other_binary"


class DerivedKind(str, enum.Enum):
    FFT = "fft"
    THUMBNAIL = "thumbnail"


# Use JSONB on postgres, JSON elsewhere (tests run against SQLite)
_JSON = JSONB().with_variant(JSON(), "sqlite")


class Artifact(Base, TimestampMixin):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # run|suite|case
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[ArtifactKind] = mapped_column(Enum(ArtifactKind, native_enum=False), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False, default=dict)


class DerivedArtifact(Base, TimestampMixin):
    __tablename__ = "derived_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_artifact_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[DerivedKind] = mapped_column(Enum(DerivedKind, native_enum=False), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    params_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
```

Update `apps/api/src/prism_api/models/__init__.py`:
```python
"""SQLAlchemy models."""
from prism_api.models.artifact import Artifact, ArtifactKind, DerivedArtifact, DerivedKind
from prism_api.models.base import Base
from prism_api.models.project import Project
from prism_api.models.run import RunStatus, RunTag, TestRun
from prism_api.models.suite import CaseStatus, TestCase, TestSuite
from prism_api.models.user import User

__all__ = [
    "Artifact",
    "ArtifactKind",
    "Base",
    "CaseStatus",
    "DerivedArtifact",
    "DerivedKind",
    "Project",
    "RunStatus",
    "RunTag",
    "TestCase",
    "TestRun",
    "TestSuite",
    "User",
]
```

- [ ] **Step 4: Run test (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_models_ingest.py -v
```

- [ ] **Step 5: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(api): ingest models — runs, suites, cases, artifacts, tags"
```

---

### Task 1.2: Alembic migration 0002

**Files:**
- Create: `apps/api/src/prism_api/migrations/versions/0002_ingest_tables.py`

- [ ] **Step 1: Write the migration**

```python
"""ingest tables: test_runs, run_tags, test_suites, test_cases, artifacts, derived_artifacts

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-20
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "test_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("junit_artifact_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_test_runs_project_id", "test_runs", ["project_id"])

    op.create_table(
        "run_tags",
        sa.Column("run_id", sa.String(36), sa.ForeignKey("test_runs.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.String(500), nullable=False),
    )
    op.create_index("ix_run_tags_kv", "run_tags", ["key", "value"])

    op.create_table(
        "test_suites",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("pass_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("fail_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("skip_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_test_suites_run_id", "test_suites", ["run_id"])

    op.create_table(
        "test_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("suite_id", sa.String(36), sa.ForeignKey("test_suites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("classname", sa.String(255), nullable=False, server_default=""),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("duration_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failure_message", sa.Text, nullable=True),
        sa.Column("failure_trace", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_test_cases_suite_id", "test_cases", ["suite_id"])

    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_type", sa.String(16), nullable=False),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("metadata_json", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_artifacts_owner", "artifacts", ["owner_type", "owner_id"])
    op.create_index("ix_artifacts_hash", "artifacts", ["content_hash"])

    op.create_table(
        "derived_artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_artifact_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("params_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_derived_source", "derived_artifacts", ["source_artifact_id"])
    op.create_index("ix_derived_params", "derived_artifacts", ["params_hash"])


def downgrade() -> None:
    op.drop_index("ix_derived_params", table_name="derived_artifacts")
    op.drop_index("ix_derived_source", table_name="derived_artifacts")
    op.drop_table("derived_artifacts")
    op.drop_index("ix_artifacts_hash", table_name="artifacts")
    op.drop_index("ix_artifacts_owner", table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_index("ix_test_cases_suite_id", table_name="test_cases")
    op.drop_table("test_cases")
    op.drop_index("ix_test_suites_run_id", table_name="test_suites")
    op.drop_table("test_suites")
    op.drop_index("ix_run_tags_kv", table_name="run_tags")
    op.drop_table("run_tags")
    op.drop_index("ix_test_runs_project_id", table_name="test_runs")
    op.drop_table("test_runs")
```

- [ ] **Step 2: Smoke-test against SQLite**

```bash
cd /home/tcollins/dev/prism/apps/api && PRISM_DATABASE_URL=sqlite:///./test.db PRISM_S3_ENDPOINT=x PRISM_S3_ACCESS_KEY=x PRISM_S3_SECRET_KEY=x PRISM_S3_BUCKET=x PRISM_REDIS_URL=x PRISM_JWT_SECRET=testsecretlongenough uv run alembic upgrade head && rm -f test.db
```
Expected: `Running upgrade 0001 -> 0002` with no errors.

- [ ] **Step 3: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/src/prism_api/migrations/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(api): migration 0002 — ingest tables"
```

---

### Task 1.3: Repositories for new models

**Files:**
- Create: `apps/api/src/prism_api/repos/runs.py` (RunRepo)
- Create: `apps/api/src/prism_api/repos/suites.py` (SuiteRepo, CaseRepo)
- Create: `apps/api/src/prism_api/repos/artifacts.py` (ArtifactRepo, DerivedRepo)
- Test: `apps/api/tests/test_ingest_repos.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_ingest_repos.py`:
```python
"""Repos for ingest-pipeline models."""
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from prism_api.models import (
    ArtifactKind,
    Base,
    CaseStatus,
    DerivedKind,
    Project,
    RunStatus,
)
from prism_api.repos.artifacts import ArtifactRepo, DerivedRepo
from prism_api.repos.projects import ProjectRepo
from prism_api.repos.runs import RunRepo
from prism_api.repos.suites import CaseRepo, SuiteRepo


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        yield s


def _seed_project(session: Session) -> Project:
    p = ProjectRepo(session).create(slug="p", name="P")
    session.flush()
    return p


def test_run_and_tag_crud(session: Session) -> None:
    p = _seed_project(session)
    run_repo = RunRepo(session)
    run = run_repo.create(project_id=p.id, name="r1", status=RunStatus.PENDING)
    session.flush()

    run_repo.add_tag(run.id, "branch", "main")
    run_repo.add_tag(run.id, "sha", "abc")
    session.commit()

    assert run_repo.get_by_id(run.id) == run
    assert run_repo.list_by_project(p.id) == [run]
    assert {(t.key, t.value) for t in run_repo.tags_for(run.id)} == {("branch", "main"), ("sha", "abc")}

    run_repo.set_status(run.id, RunStatus.PASS)
    session.commit()
    assert run_repo.get_by_id(run.id).status == RunStatus.PASS


def test_suite_and_case_crud(session: Session) -> None:
    p = _seed_project(session)
    run = RunRepo(session).create(project_id=p.id, name="r", status=RunStatus.PENDING)
    session.flush()

    suite = SuiteRepo(session).create(run_id=run.id, name="dsp")
    session.flush()

    case = CaseRepo(session).create(
        suite_id=suite.id, classname="codec", name="sine", status=CaseStatus.PASS, duration_ms=5
    )
    session.commit()

    assert SuiteRepo(session).list_by_run(run.id) == [suite]
    assert CaseRepo(session).list_by_suite(suite.id) == [case]


def test_artifact_dedup_by_hash(session: Session) -> None:
    p = _seed_project(session)
    run = RunRepo(session).create(project_id=p.id, name="r", status=RunStatus.PENDING)
    session.flush()

    repo = ArtifactRepo(session)
    first = repo.create(
        owner_type="run",
        owner_id=run.id,
        kind=ArtifactKind.WAVEFORM_CSV,
        filename="a.csv",
        size_bytes=10,
        content_hash="h" * 64,
        storage_key="raw/hh/" + "h" * 64,
    )
    session.flush()

    # Same hash, different filename -> separate row but same storage_key
    second = repo.create(
        owner_type="run",
        owner_id=run.id,
        kind=ArtifactKind.WAVEFORM_CSV,
        filename="b.csv",
        size_bytes=10,
        content_hash="h" * 64,
        storage_key="raw/hh/" + "h" * 64,
    )
    session.commit()

    assert first.id != second.id
    assert first.storage_key == second.storage_key
    assert [a.filename for a in repo.list_by_owner("run", run.id)] == ["a.csv", "b.csv"]


def test_derived_artifact_lookup(session: Session) -> None:
    p = _seed_project(session)
    run = RunRepo(session).create(project_id=p.id, name="r", status=RunStatus.PENDING)
    session.flush()
    art = ArtifactRepo(session).create(
        owner_type="run", owner_id=run.id, kind=ArtifactKind.WAVEFORM_CSV,
        filename="a.csv", size_bytes=10, content_hash="h" * 64, storage_key="k",
    )
    session.flush()

    dr = DerivedRepo(session)
    d = dr.create(source_artifact_id=art.id, kind=DerivedKind.FFT, storage_key="derived/fft/x.npy", params_hash="p" * 32)
    session.commit()

    assert dr.find(source_artifact_id=art.id, kind=DerivedKind.FFT, params_hash="p" * 32) == d
    assert dr.find(source_artifact_id=art.id, kind=DerivedKind.FFT, params_hash="other") is None
```

- [ ] **Step 2: Run test (FAIL)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_ingest_repos.py -v
```

- [ ] **Step 3: Implement repos**

`apps/api/src/prism_api/repos/runs.py`:
```python
"""Run repository."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from prism_api.models.run import RunStatus, RunTag, TestRun


class RunRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, project_id: str, name: str, status: RunStatus, created_by: str | None = None) -> TestRun:
        run = TestRun(project_id=project_id, name=name, status=status, created_by=created_by)
        self._session.add(run)
        self._session.flush()
        return run

    def get_by_id(self, run_id: str) -> TestRun | None:
        return self._session.get(TestRun, run_id)

    def list_by_project(self, project_id: str) -> list[TestRun]:
        return list(
            self._session.execute(
                select(TestRun).where(TestRun.project_id == project_id).order_by(TestRun.created_at.desc())
            ).scalars()
        )

    def set_status(self, run_id: str, status: RunStatus) -> None:
        run = self._session.get(TestRun, run_id)
        if run is not None:
            run.status = status

    def set_junit_artifact(self, run_id: str, artifact_id: str) -> None:
        run = self._session.get(TestRun, run_id)
        if run is not None:
            run.junit_artifact_id = artifact_id

    def add_tag(self, run_id: str, key: str, value: str) -> RunTag:
        tag = RunTag(run_id=run_id, key=key, value=value)
        self._session.merge(tag)
        return tag

    def tags_for(self, run_id: str) -> list[RunTag]:
        return list(
            self._session.execute(select(RunTag).where(RunTag.run_id == run_id)).scalars()
        )
```

`apps/api/src/prism_api/repos/suites.py`:
```python
"""Suite and case repositories."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from prism_api.models.suite import CaseStatus, TestCase, TestSuite


class SuiteRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        run_id: str,
        name: str,
        pass_count: int = 0,
        fail_count: int = 0,
        error_count: int = 0,
        skip_count: int = 0,
        duration_ms: int = 0,
    ) -> TestSuite:
        suite = TestSuite(
            run_id=run_id,
            name=name,
            pass_count=pass_count,
            fail_count=fail_count,
            error_count=error_count,
            skip_count=skip_count,
            duration_ms=duration_ms,
        )
        self._session.add(suite)
        self._session.flush()
        return suite

    def list_by_run(self, run_id: str) -> list[TestSuite]:
        return list(self._session.execute(select(TestSuite).where(TestSuite.run_id == run_id)).scalars())


class CaseRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        suite_id: str,
        classname: str,
        name: str,
        status: CaseStatus,
        duration_ms: int = 0,
        failure_message: str | None = None,
        failure_trace: str | None = None,
    ) -> TestCase:
        case = TestCase(
            suite_id=suite_id,
            classname=classname,
            name=name,
            status=status,
            duration_ms=duration_ms,
            failure_message=failure_message,
            failure_trace=failure_trace,
        )
        self._session.add(case)
        self._session.flush()
        return case

    def list_by_suite(self, suite_id: str) -> list[TestCase]:
        return list(self._session.execute(select(TestCase).where(TestCase.suite_id == suite_id)).scalars())
```

`apps/api/src/prism_api/repos/artifacts.py`:
```python
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
```

- [ ] **Step 4: Run test (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_ingest_repos.py -v
```

- [ ] **Step 5: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(api): repos for runs, suites, cases, artifacts"
```

---

## Phase 2: MinIO storage layer

### Task 2.1: Storage wrapper

**Files:**
- Create: `apps/api/src/prism_api/storage.py`
- Test: `apps/api/tests/test_storage.py`

- [ ] **Step 1: Add `moto` to dev dependencies**

Edit `apps/api/pyproject.toml` `[dependency-groups] dev` list to include `"moto[s3]>=5.0"`. Run `cd /home/tcollins/dev/prism/apps/api && uv sync --group dev`.

- [ ] **Step 2: Write the failing test**

`apps/api/tests/test_storage.py`:
```python
"""Storage layer tests using moto (in-process S3)."""
from io import BytesIO

import boto3
import pytest
from moto import mock_aws

from prism_api.storage import ObjectStorage, hash_bytes


@pytest.fixture
def storage():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="prism")
        yield ObjectStorage(client=client, bucket="prism")


def test_hash_bytes_is_sha256_hex():
    assert hash_bytes(b"hello") == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_put_and_get_round_trip(storage: ObjectStorage):
    payload = b"some bytes"
    h = hash_bytes(payload)
    key = storage.put_raw(payload, filename="x.csv")
    assert key.startswith("raw/")
    assert h in key

    body, _size = storage.get(key)
    assert body.read() == payload


def test_put_raw_is_idempotent(storage: ObjectStorage):
    payload = b"abc"
    k1 = storage.put_raw(payload, filename="x.csv")
    k2 = storage.put_raw(payload, filename="y.csv")  # same bytes, different filename
    assert k1 == k2  # content-addressed -> same key


def test_ensure_bucket_is_idempotent(storage: ObjectStorage):
    # Bucket already exists; method must not raise
    storage.ensure_bucket()
    storage.ensure_bucket()
```

- [ ] **Step 3: Run test (FAIL — ModuleNotFoundError)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_storage.py -v
```

- [ ] **Step 4: Implement storage**

`apps/api/src/prism_api/storage.py`:
```python
"""MinIO / S3 storage wrapper — thin abstraction over boto3."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import IO, TYPE_CHECKING

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client
else:
    S3Client = object  # type: ignore[assignment,misc]


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class ObjectStorage:
    """Content-addressed object store wrapper."""
    client: S3Client
    bucket: str

    def ensure_bucket(self) -> None:
        existing = {b["Name"] for b in self.client.list_buckets().get("Buckets", [])}
        if self.bucket in existing:
            return
        self.client.create_bucket(Bucket=self.bucket)

    def put_raw(self, data: bytes, *, filename: str) -> str:
        """Store bytes at content-addressed key; return the key."""
        h = hash_bytes(data)
        key = f"raw/{h[:2]}/{h}"
        # S3 put is idempotent for same content; skip existence probe to save a round-trip
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, Metadata={"filename": filename})
        return key

    def put_at(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> None:
        """Write bytes to an explicit key (used for derived artifacts)."""
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> tuple[IO[bytes], int]:
        """Return (body stream, size)."""
        resp = self.client.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"], int(resp.get("ContentLength", 0))

    def get_bytes(self, key: str) -> bytes:
        body, _ = self.get(key)
        return body.read()

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except self.client.exceptions.ClientError:
            return False

    def presigned_url(self, key: str, *, expires_in: int = 900) -> str:
        return self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires_in
        )
```

- [ ] **Step 5: Run test (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_storage.py -v
```
Expected: 4/4 PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(api): ObjectStorage wrapper with content-addressed put_raw"
```

---

### Task 2.2: Storage factory & bootstrap

**Files:**
- Modify: `apps/api/src/prism_api/storage.py` (add `build_storage(settings)` helper)
- Modify: `apps/api/src/prism_api/cli.py` (add `ensure-bucket` subcommand)
- Modify: `apps/api/docker-entrypoint.sh` (call `python -m prism_api.cli ensure-bucket`)
- Test: `apps/api/tests/test_storage_factory.py`

- [ ] **Step 1: Add failing test**

`apps/api/tests/test_storage_factory.py`:
```python
from unittest.mock import patch

from prism_api.config import Settings
from prism_api.storage import build_storage


def _settings(**overrides) -> Settings:
    base = dict(
        database_url="sqlite:///:memory:",
        s3_endpoint="http://minio:9000",
        s3_access_key="ak",
        s3_secret_key="sk",
        s3_bucket="prism",
        redis_url="redis://r:6379/0",
        jwt_secret="testsecretlongenough",
    )
    base.update(overrides)
    return Settings(**base)  # type: ignore[call-arg]


def test_build_storage_uses_settings_endpoint_and_creds():
    with patch("prism_api.storage.boto3.client") as mock_client:
        build_storage(_settings())
        kwargs = mock_client.call_args.kwargs
        assert kwargs["endpoint_url"] == "http://minio:9000"
        assert kwargs["aws_access_key_id"] == "ak"
        assert kwargs["aws_secret_access_key"] == "sk"
```

- [ ] **Step 2: Run test (FAIL — `build_storage` does not exist)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_storage_factory.py -v
```

- [ ] **Step 3: Implement factory**

Append to `apps/api/src/prism_api/storage.py`:
```python
import boto3

from prism_api.config import Settings


def build_storage(settings: Settings) -> ObjectStorage:
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name="us-east-1",
    )
    return ObjectStorage(client=client, bucket=settings.s3_bucket)
```

- [ ] **Step 4: Add `ensure-bucket` CLI command**

Update `apps/api/src/prism_api/cli.py`:
```python
"""Command-line entry points for ops tasks."""
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from prism_api.bootstrap import ensure_bootstrap_admin
from prism_api.config import Settings, get_settings
from prism_api.storage import build_storage


def bootstrap_admin(settings: Settings | None = None) -> None:
    s = settings or get_settings()
    engine = create_engine(s.database_url)
    with sessionmaker(bind=engine)() as session:
        ensure_bootstrap_admin(session, email=s.admin_email, password=s.admin_password)
        session.commit()


def ensure_bucket(settings: Settings | None = None) -> None:
    s = settings or get_settings()
    storage = build_storage(s)
    storage.ensure_bucket()


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: prism-api <bootstrap-admin|ensure-bucket>", file=sys.stderr)
        return 2
    cmd = sys.argv[1]
    if cmd == "bootstrap-admin":
        bootstrap_admin()
        return 0
    if cmd == "ensure-bucket":
        ensure_bucket()
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Update entrypoint**

`apps/api/docker-entrypoint.sh`:
```sh
#!/bin/sh
set -e
alembic upgrade head
python -m prism_api.cli bootstrap-admin
python -m prism_api.cli ensure-bucket
exec "$@"
```

- [ ] **Step 6: Run all tests**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest -v
```
Expected: all passing.

- [ ] **Step 7: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(api): storage factory + ensure-bucket on entrypoint"
```

---

## Phase 3: Parsers

### Task 3.1: JUnit parser

**Files:**
- Create: `apps/api/src/prism_api/parsers/__init__.py` (empty)
- Create: `apps/api/src/prism_api/parsers/junit.py`
- Create: `apps/api/tests/fixtures/sample-junit.xml`
- Create: `apps/api/tests/test_parsers_junit.py`

- [ ] **Step 1: Write the sample fixture**

`apps/api/tests/fixtures/sample-junit.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite name="dsp" tests="3" failures="1" errors="0" skipped="0" time="0.42">
    <testcase classname="codec" name="sine_sweep_1khz" time="0.12"/>
    <testcase classname="codec" name="sine_sweep_5khz" time="0.14">
      <failure message="expected SNR &gt;60dB, got 58.3dB">AssertionError traceback...</failure>
    </testcase>
    <testcase classname="latency" name="round_trip" time="0.16"/>
  </testsuite>
  <testsuite name="api" tests="1" failures="0" errors="0" skipped="0" time="0.05">
    <testcase classname="upload" name="happy_path" time="0.05"/>
  </testsuite>
</testsuites>
```

- [ ] **Step 2: Write the failing test**

`apps/api/tests/test_parsers_junit.py`:
```python
from pathlib import Path

from prism_api.parsers.junit import ParsedCase, ParsedSuite, parse_junit_xml


def test_parse_sample() -> None:
    xml = Path(__file__).parent / "fixtures" / "sample-junit.xml"
    result = parse_junit_xml(xml.read_bytes())
    assert len(result) == 2
    dsp, api = result
    assert isinstance(dsp, ParsedSuite)
    assert dsp.name == "dsp"
    assert dsp.pass_count == 2
    assert dsp.fail_count == 1
    assert dsp.error_count == 0
    assert dsp.skip_count == 0
    assert len(dsp.cases) == 3
    sweep = next(c for c in dsp.cases if c.name == "sine_sweep_5khz")
    assert isinstance(sweep, ParsedCase)
    assert sweep.classname == "codec"
    assert sweep.status == "fail"
    assert "SNR" in (sweep.failure_message or "")
    assert api.name == "api"
    assert api.pass_count == 1


def test_parse_empty_wrapper() -> None:
    empty = b'<?xml version="1.0"?><testsuites></testsuites>'
    assert parse_junit_xml(empty) == []
```

- [ ] **Step 3: Run test (FAIL)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_parsers_junit.py -v
```

- [ ] **Step 4: Implement parser**

`apps/api/src/prism_api/parsers/__init__.py`: empty.

`apps/api/src/prism_api/parsers/junit.py`:
```python
"""JUnit XML parser — thin wrapper over `junitparser`."""
from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO

from junitparser import Error, Failure, JUnitXml, Skipped, TestCase as JTCase


@dataclass
class ParsedCase:
    classname: str
    name: str
    status: str  # pass | fail | error | skip
    duration_ms: int
    failure_message: str | None = None
    failure_trace: str | None = None


@dataclass
class ParsedSuite:
    name: str
    pass_count: int = 0
    fail_count: int = 0
    error_count: int = 0
    skip_count: int = 0
    duration_ms: int = 0
    cases: list[ParsedCase] = field(default_factory=list)


def _case_status(case: JTCase) -> tuple[str, str | None, str | None]:
    for result in case.result or []:
        if isinstance(result, Failure):
            return "fail", result.message, (result.text or None)
        if isinstance(result, Error):
            return "error", result.message, (result.text or None)
        if isinstance(result, Skipped):
            return "skip", result.message, None
    return "pass", None, None


def parse_junit_xml(data: bytes) -> list[ParsedSuite]:
    xml = JUnitXml.fromstring(BytesIO(data).read())
    # `JUnitXml.fromstring` returns either a TestSuites root or a single TestSuite
    suites_iter = xml if hasattr(xml, "__iter__") else [xml]
    out: list[ParsedSuite] = []
    for suite in suites_iter:
        parsed = ParsedSuite(name=suite.name or "", duration_ms=int((suite.time or 0) * 1000))
        for c in suite:
            status, msg, trace = _case_status(c)
            duration_ms = int((c.time or 0) * 1000)
            parsed.cases.append(
                ParsedCase(
                    classname=c.classname or "",
                    name=c.name,
                    status=status,
                    duration_ms=duration_ms,
                    failure_message=msg,
                    failure_trace=trace,
                )
            )
            if status == "pass":
                parsed.pass_count += 1
            elif status == "fail":
                parsed.fail_count += 1
            elif status == "error":
                parsed.error_count += 1
            else:
                parsed.skip_count += 1
        out.append(parsed)
    return out
```

- [ ] **Step 5: Run test (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_parsers_junit.py -v
```

- [ ] **Step 6: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(api): JUnit XML parser"
```

---

### Task 3.2: Artifact kind detector

**Files:**
- Create: `apps/api/src/prism_api/parsers/detect.py`
- Test: `apps/api/tests/test_parsers_detect.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_parsers_detect.py`:
```python
from prism_api.models import ArtifactKind
from prism_api.parsers.detect import detect_kind


def test_junit_xml() -> None:
    assert detect_kind("results.xml", b'<?xml version="1.0"?><testsuites/>') == ArtifactKind.JUNIT_XML


def test_waveform_csv() -> None:
    assert detect_kind("sine.csv", b"0.0\n0.1\n0.2\n") == ArtifactKind.WAVEFORM_CSV


def test_waveform_npy() -> None:
    # magic: \x93NUMPY
    assert detect_kind("wave.npy", b"\x93NUMPY\x01\x00") == ArtifactKind.WAVEFORM_NPY


def test_waveform_hdf5() -> None:
    # magic: \x89HDF\r\n\x1a\n
    assert detect_kind("data.h5", b"\x89HDF\r\n\x1a\n") == ArtifactKind.WAVEFORM_HDF5


def test_wav_audio() -> None:
    assert detect_kind("clip.wav", b"RIFF....WAVEfmt ") == ArtifactKind.WAV_AUDIO


def test_png_image() -> None:
    assert detect_kind("plot.png", b"\x89PNG\r\n\x1a\n") == ArtifactKind.IMAGE_PNG


def test_text_log() -> None:
    assert detect_kind("run.log", b"2026-04-20 12:00:00 info\n") == ArtifactKind.LOG_TEXT


def test_other_binary() -> None:
    assert detect_kind("mystery.bin", b"\x00\x01\x02\x03") == ArtifactKind.OTHER_BINARY


def test_extension_overrides_ambiguous_magic() -> None:
    # An .xml file should still be JUnit even if content is missing leading <?xml
    assert detect_kind("x.xml", b"<testsuites><testsuite/></testsuites>") == ArtifactKind.JUNIT_XML
```

- [ ] **Step 2: Run test (FAIL)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_parsers_detect.py -v
```

- [ ] **Step 3: Implement detector**

`apps/api/src/prism_api/parsers/detect.py`:
```python
"""Artifact kind detection — extension + magic bytes."""
from pathlib import PurePosixPath

from prism_api.models import ArtifactKind


def _has_prefix(data: bytes, prefix: bytes) -> bool:
    return data.startswith(prefix)


def _is_probably_text(data: bytes) -> bool:
    sample = data[:1024]
    return all(32 <= b < 127 or b in (9, 10, 13) for b in sample)


def detect_kind(filename: str, head: bytes) -> ArtifactKind:
    """Detect artifact kind by trusting magic bytes first, then extension, then content."""
    # Magic-byte fast paths
    if _has_prefix(head, b"\x93NUMPY"):
        return ArtifactKind.WAVEFORM_NPY
    if _has_prefix(head, b"\x89HDF\r\n\x1a\n"):
        return ArtifactKind.WAVEFORM_HDF5
    if _has_prefix(head, b"\x89PNG\r\n\x1a\n"):
        return ArtifactKind.IMAGE_PNG
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return ArtifactKind.WAV_AUDIO

    # Extension-based
    suffix = PurePosixPath(filename).suffix.lower()
    if suffix == ".xml":
        return ArtifactKind.JUNIT_XML
    if suffix == ".csv":
        return ArtifactKind.WAVEFORM_CSV
    if suffix in {".npy"}:
        return ArtifactKind.WAVEFORM_NPY
    if suffix in {".h5", ".hdf5"}:
        return ArtifactKind.WAVEFORM_HDF5
    if suffix == ".wav":
        return ArtifactKind.WAV_AUDIO
    if suffix == ".png":
        return ArtifactKind.IMAGE_PNG
    if suffix in {".log", ".txt"}:
        return ArtifactKind.LOG_TEXT

    # Content-based fallbacks
    if _is_probably_text(head):
        return ArtifactKind.LOG_TEXT
    return ArtifactKind.OTHER_BINARY
```

- [ ] **Step 4: Run test (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_parsers_detect.py -v
```

- [ ] **Step 5: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(api): artifact kind detector (magic bytes + extension)"
```

---

### Task 3.3: Artifact filename convention parser

The worker links each uploaded file to a suite/case/run by parsing its filename per the convention `{suite}__{case}__{label}.{ext}`. If only one `__` separator is present, the file attaches to a suite; if none, it attaches to the run.

**Files:**
- Create: `apps/api/src/prism_api/parsers/filename.py`
- Test: `apps/api/tests/test_parsers_filename.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_parsers_filename.py`:
```python
from prism_api.parsers.filename import ArtifactOwner, parse_artifact_filename


def test_run_level() -> None:
    got = parse_artifact_filename("readme.log")
    assert got == ArtifactOwner(scope="run", suite=None, case=None, label="readme", ext=".log")


def test_suite_level() -> None:
    got = parse_artifact_filename("dsp__suite-log.log")
    assert got == ArtifactOwner(scope="suite", suite="dsp", case=None, label="suite-log", ext=".log")


def test_case_level() -> None:
    got = parse_artifact_filename("dsp__sine_sweep_1khz__waveform.csv")
    assert got == ArtifactOwner(scope="case", suite="dsp", case="sine_sweep_1khz", label="waveform", ext=".csv")


def test_case_level_with_label_underscores() -> None:
    got = parse_artifact_filename("dsp__sine__fft_magnitude.csv")
    # label can contain single underscores — only `__` delimits scopes
    assert got.scope == "case"
    assert got.case == "sine"
    assert got.label == "fft_magnitude"
```

- [ ] **Step 2: Run test (FAIL)**

- [ ] **Step 3: Implement parser**

`apps/api/src/prism_api/parsers/filename.py`:
```python
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
        return ArtifactOwner(scope="case", suite=parts[0], case=parts[1], label="__".join(parts[2:]), ext=ext)
    if len(parts) == 2:
        return ArtifactOwner(scope="suite", suite=parts[0], case=None, label=parts[1], ext=ext)
    return ArtifactOwner(scope="run", suite=None, case=None, label=parts[0], ext=ext)
```

- [ ] **Step 4: Run test (PASS)**

- [ ] **Step 5: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(api): artifact filename convention parser"
```

---

## Phase 4: Celery worker

### Task 4.1: Celery app

**Files:**
- Create: `apps/api/src/prism_api/worker/__init__.py` (empty)
- Create: `apps/api/src/prism_api/worker/celery_app.py`
- Test: `apps/api/tests/test_celery_app.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_celery_app.py`:
```python
from prism_api.worker.celery_app import build_celery
from prism_api.config import Settings


def _s() -> Settings:
    return Settings(  # type: ignore[call-arg]
        database_url="sqlite:///:memory:",
        s3_endpoint="x",
        s3_access_key="x",
        s3_secret_key="x",
        s3_bucket="x",
        redis_url="redis://localhost:6379/0",
        jwt_secret="testsecretlongenough",
    )


def test_celery_app_configured_from_settings():
    app = build_celery(_s())
    assert app.conf.broker_url == "redis://localhost:6379/0"
    assert app.conf.result_backend == "redis://localhost:6379/0"
    assert app.conf.task_serializer == "json"
```

- [ ] **Step 2: Implement celery app**

`apps/api/src/prism_api/worker/__init__.py`: empty.

`apps/api/src/prism_api/worker/celery_app.py`:
```python
"""Celery application factory."""
from celery import Celery

from prism_api.config import Settings, get_settings


def build_celery(settings: Settings | None = None) -> Celery:
    s = settings or get_settings()
    app = Celery("prism", broker=s.redis_url, backend=s.redis_url)
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
    )
    # Ensure tasks module is imported
    app.autodiscover_tasks(["prism_api.worker"])
    return app


celery_app = build_celery()
```

- [ ] **Step 3: Run test (PASS)**

- [ ] **Step 4: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(api): Celery app factory"
```

---

### Task 4.2: Ingest task

**Files:**
- Create: `apps/api/src/prism_api/worker/tasks.py`
- Create: `apps/api/src/prism_api/ingest.py` (orchestration logic — testable without Celery)
- Test: `apps/api/tests/test_ingest_flow.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_ingest_flow.py`:
```python
"""End-to-end ingest flow using in-memory SQLite + moto S3 + synthetic archive."""
import io
import zipfile
from collections.abc import Iterator
from pathlib import Path

import boto3
import numpy as np
import pytest
from moto import mock_aws
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from prism_api.ingest import IngestInputs, ingest_run
from prism_api.models import Base
from prism_api.models.run import RunStatus
from prism_api.repos.artifacts import ArtifactRepo
from prism_api.repos.projects import ProjectRepo
from prism_api.repos.runs import RunRepo
from prism_api.repos.suites import CaseRepo, SuiteRepo
from prism_api.storage import ObjectStorage


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        yield s


@pytest.fixture
def storage() -> Iterator[ObjectStorage]:
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="prism")
        yield ObjectStorage(client=client, bucket="prism")


def _make_archive() -> bytes:
    """Create an in-memory zip with a run-level log and a case-level CSV waveform."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.log", "run context goes here\n")
        samples = np.sin(np.linspace(0, 2 * np.pi, 512)).astype(np.float32)
        zf.writestr("dsp__sine_sweep_1khz__waveform.csv", "\n".join(str(x) for x in samples))
    return buf.getvalue()


def test_ingest_end_to_end(session: Session, storage: ObjectStorage) -> None:
    project = ProjectRepo(session).create(slug="audio", name="Audio")
    session.flush()

    junit_xml = (Path(__file__).parent / "fixtures" / "sample-junit.xml").read_bytes()
    archive = _make_archive()

    run = RunRepo(session).create(project_id=project.id, name="r1", status=RunStatus.PENDING)
    session.flush()

    ingest_run(
        IngestInputs(
            run_id=run.id,
            junit_xml=junit_xml,
            archive=archive,
        ),
        session=session,
        storage=storage,
    )
    session.commit()

    # Suites + cases created
    suites = SuiteRepo(session).list_by_run(run.id)
    assert {s.name for s in suites} == {"dsp", "api"}

    dsp = next(s for s in suites if s.name == "dsp")
    cases = CaseRepo(session).list_by_suite(dsp.id)
    assert {c.name for c in cases} == {"sine_sweep_1khz", "sine_sweep_5khz", "round_trip"}

    # Run-level log artifact exists
    run_artifacts = ArtifactRepo(session).list_by_owner("run", run.id)
    assert any(a.filename == "readme.log" for a in run_artifacts)
    assert any(a.kind.value == "junit_xml" for a in run_artifacts)

    # Case-level waveform CSV
    sine_1khz = next(c for c in cases if c.name == "sine_sweep_1khz")
    case_artifacts = ArtifactRepo(session).list_by_owner("case", sine_1khz.id)
    assert [a.filename for a in case_artifacts] == ["dsp__sine_sweep_1khz__waveform.csv"]
    assert case_artifacts[0].kind.value == "waveform_csv"

    # Run status flipped to `mixed` (sample JUnit has 1 failure out of 4)
    assert RunRepo(session).get_by_id(run.id).status == RunStatus.MIXED

    # junit_artifact_id set
    assert RunRepo(session).get_by_id(run.id).junit_artifact_id is not None


def test_ingest_all_pass_sets_pass_status(session: Session, storage: ObjectStorage) -> None:
    project = ProjectRepo(session).create(slug="audio", name="Audio")
    session.flush()

    all_pass_junit = b"""<?xml version="1.0"?>
<testsuites>
  <testsuite name="api" tests="1" failures="0" errors="0" skipped="0" time="0.05">
    <testcase classname="x" name="y" time="0.05"/>
  </testsuite>
</testsuites>"""

    run = RunRepo(session).create(project_id=project.id, name="r-ok", status=RunStatus.PENDING)
    session.flush()

    ingest_run(
        IngestInputs(run_id=run.id, junit_xml=all_pass_junit, archive=None),
        session=session,
        storage=storage,
    )
    session.commit()
    assert RunRepo(session).get_by_id(run.id).status == RunStatus.PASS


def test_ingest_without_junit_errors_the_run(session: Session, storage: ObjectStorage) -> None:
    project = ProjectRepo(session).create(slug="audio", name="Audio")
    session.flush()
    run = RunRepo(session).create(project_id=project.id, name="r-bad", status=RunStatus.PENDING)
    session.flush()

    ingest_run(
        IngestInputs(run_id=run.id, junit_xml=b"<not valid xml", archive=None),
        session=session,
        storage=storage,
    )
    session.commit()
    assert RunRepo(session).get_by_id(run.id).status == RunStatus.ERROR
```

- [ ] **Step 2: Run test (FAIL — `prism_api.ingest` missing)**

- [ ] **Step 3: Implement orchestration**

`apps/api/src/prism_api/ingest.py`:
```python
"""Ingest orchestration — pure function that the worker task wraps."""
from __future__ import annotations

import io
import logging
import zipfile
from dataclasses import dataclass

from sqlalchemy.orm import Session

from prism_api.models import ArtifactKind, CaseStatus, RunStatus, TestCase, TestSuite
from prism_api.parsers.detect import detect_kind
from prism_api.parsers.filename import ArtifactOwner, parse_artifact_filename
from prism_api.parsers.junit import ParsedSuite, parse_junit_xml
from prism_api.repos.artifacts import ArtifactRepo
from prism_api.repos.runs import RunRepo
from prism_api.repos.suites import CaseRepo, SuiteRepo
from prism_api.storage import ObjectStorage

logger = logging.getLogger(__name__)

_STATUS_MAP = {"pass": CaseStatus.PASS, "fail": CaseStatus.FAIL, "error": CaseStatus.ERROR, "skip": CaseStatus.SKIP}


@dataclass
class IngestInputs:
    run_id: str
    junit_xml: bytes
    archive: bytes | None = None


def _derive_run_status(suites: list[ParsedSuite]) -> RunStatus:
    fail = sum(s.fail_count for s in suites)
    err = sum(s.error_count for s in suites)
    passed = sum(s.pass_count for s in suites)
    if err > 0:
        return RunStatus.ERROR
    if fail == 0 and passed > 0:
        return RunStatus.PASS
    if fail > 0 and passed == 0:
        return RunStatus.FAIL
    return RunStatus.MIXED


def ingest_run(inputs: IngestInputs, *, session: Session, storage: ObjectStorage) -> None:
    runs = RunRepo(session)
    suites_repo = SuiteRepo(session)
    cases_repo = CaseRepo(session)
    artifacts = ArtifactRepo(session)

    # 1) Store the JUnit XML as a run-level artifact
    junit_key = storage.put_raw(inputs.junit_xml, filename="junit.xml")
    junit_artifact = artifacts.create(
        owner_type="run",
        owner_id=inputs.run_id,
        kind=ArtifactKind.JUNIT_XML,
        filename="junit.xml",
        size_bytes=len(inputs.junit_xml),
        content_hash=junit_key.rsplit("/", 1)[-1],
        storage_key=junit_key,
    )
    runs.set_junit_artifact(inputs.run_id, junit_artifact.id)

    # 2) Parse JUnit
    try:
        parsed_suites = parse_junit_xml(inputs.junit_xml)
    except Exception as exc:  # noqa: BLE001
        logger.exception("failed to parse JUnit XML for run %s: %s", inputs.run_id, exc)
        runs.set_status(inputs.run_id, RunStatus.ERROR)
        return

    # 3) Create suites + cases; build lookup maps for artifact attachment
    suite_by_name: dict[str, TestSuite] = {}
    case_by_key: dict[tuple[str, str], TestCase] = {}
    for ps in parsed_suites:
        suite = suites_repo.create(
            run_id=inputs.run_id,
            name=ps.name,
            pass_count=ps.pass_count,
            fail_count=ps.fail_count,
            error_count=ps.error_count,
            skip_count=ps.skip_count,
            duration_ms=ps.duration_ms,
        )
        suite_by_name[ps.name] = suite
        for pc in ps.cases:
            case = cases_repo.create(
                suite_id=suite.id,
                classname=pc.classname,
                name=pc.name,
                status=_STATUS_MAP[pc.status],
                duration_ms=pc.duration_ms,
                failure_message=pc.failure_message,
                failure_trace=pc.failure_trace,
            )
            case_by_key[(ps.name, pc.name)] = case

    # 4) Extract archive and attach artifacts
    if inputs.archive:
        with zipfile.ZipFile(io.BytesIO(inputs.archive)) as zf:
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                data = zf.read(name)
                owner = parse_artifact_filename(name.rsplit("/", 1)[-1])
                kind = detect_kind(name, data[:512])
                key = storage.put_raw(data, filename=name)
                owner_type, owner_id = _resolve_owner(owner, inputs.run_id, suite_by_name, case_by_key)
                artifacts.create(
                    owner_type=owner_type,
                    owner_id=owner_id,
                    kind=kind,
                    filename=name,
                    size_bytes=len(data),
                    content_hash=key.rsplit("/", 1)[-1],
                    storage_key=key,
                )

    # 5) Set final run status
    runs.set_status(inputs.run_id, _derive_run_status(parsed_suites))


def _resolve_owner(
    owner: ArtifactOwner,
    run_id: str,
    suite_by_name: dict[str, TestSuite],
    case_by_key: dict[tuple[str, str], TestCase],
) -> tuple[str, str]:
    if owner.scope == "case" and owner.suite and owner.case:
        case = case_by_key.get((owner.suite, owner.case))
        if case is not None:
            return "case", case.id
    if owner.scope in ("case", "suite") and owner.suite:
        suite = suite_by_name.get(owner.suite)
        if suite is not None:
            return "suite", suite.id
    return "run", run_id
```

- [ ] **Step 4: Implement the Celery task wrapper**

`apps/api/src/prism_api/worker/tasks.py`:
```python
"""Celery tasks."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from prism_api.config import get_settings
from prism_api.ingest import IngestInputs, ingest_run
from prism_api.storage import build_storage
from prism_api.worker.celery_app import celery_app


@celery_app.task(name="prism.ingest_run")
def run_ingest(run_id: str, junit_xml_key: str, archive_key: str | None) -> None:
    settings = get_settings()
    storage = build_storage(settings)
    engine = create_engine(settings.database_url)
    junit_xml = storage.get_bytes(junit_xml_key)
    archive = storage.get_bytes(archive_key) if archive_key else None
    with sessionmaker(bind=engine)() as session:
        ingest_run(
            IngestInputs(run_id=run_id, junit_xml=junit_xml, archive=archive),
            session=session,
            storage=storage,
        )
        session.commit()
```

- [ ] **Step 5: Run tests (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_ingest_flow.py -v
```
Expected: 3/3 PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(api): ingest pipeline — suites/cases + artifact attachment"
```

---

## Phase 5: Upload endpoint

### Task 5.1: Upload schemas

**Files:**
- Create: `apps/api/src/prism_api/schemas/run.py`

- [ ] **Step 1: Write the schemas**

`apps/api/src/prism_api/schemas/run.py`:
```python
"""Run request/response schemas."""
from datetime import datetime

from pydantic import BaseModel, Field


class RunTagOut(BaseModel):
    key: str
    value: str


class RunOut(BaseModel):
    id: str
    project_id: str
    name: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    junit_artifact_id: str | None
    tags: list[RunTagOut] = Field(default_factory=list)


class CreateRunMetadata(BaseModel):
    project_slug: str
    name: str
    tags: dict[str, str] = Field(default_factory=dict)
    started_at: datetime | None = None
```

- [ ] **Step 2: Commit (pair this commit with the router task)**

No commit yet — fold into next task to keep commit topical.

---

### Task 5.2: POST /runs endpoint

**Files:**
- Create: `apps/api/src/prism_api/routers/runs.py`
- Modify: `apps/api/src/prism_api/main.py` (include runs router)
- Test: `apps/api/tests/test_runs_router.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_runs_router.py`:
```python
"""Runs router test — uses a monkeypatched celery task so ingest runs inline."""
import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _login(client: TestClient) -> None:
    r = client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    assert r.status_code == 200


def _seed_project(client: TestClient) -> None:
    r = client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    assert r.status_code == 201


def _sample_archive() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.log", "hello\n")
    return buf.getvalue()


@pytest.fixture
def patch_ingest(monkeypatch, db_session, storage_fixture):
    """Replace the celery delay with an inline call, and provide the same storage to both sides."""
    from prism_api.routers import runs as runs_module

    def fake_enqueue(run_id: str, junit_xml: bytes, archive: bytes | None) -> None:
        from prism_api.ingest import IngestInputs, ingest_run
        ingest_run(
            IngestInputs(run_id=run_id, junit_xml=junit_xml, archive=archive),
            session=db_session,
            storage=storage_fixture,
        )
        db_session.commit()

    monkeypatch.setattr(runs_module, "enqueue_ingest", fake_enqueue)
    return None


def test_upload_run_with_archive(client: TestClient, seed_admin, patch_ingest) -> None:
    _login(client)
    _seed_project(client)

    junit = (Path(__file__).parent / "fixtures" / "sample-junit.xml").read_bytes()
    archive = _sample_archive()
    metadata = {"project_slug": "audio", "name": "nightly-42", "tags": {"branch": "main"}}

    resp = client.post(
        "/api/v1/runs",
        files={
            "junit": ("junit.xml", junit, "application/xml"),
            "archive": ("artifacts.zip", archive, "application/zip"),
        },
        data={"metadata": json.dumps(metadata)},
    )
    assert resp.status_code == 201, resp.text
    run = resp.json()
    assert run["name"] == "nightly-42"
    assert run["status"] == "mixed"
    assert {t["key"]: t["value"] for t in run["tags"]} == {"branch": "main"}


def test_upload_requires_auth(client: TestClient) -> None:
    resp = client.post("/api/v1/runs", files={"junit": ("j.xml", b"<testsuites/>", "application/xml")}, data={"metadata": "{}"})
    assert resp.status_code == 401


def test_upload_unknown_project(client: TestClient, seed_admin, patch_ingest) -> None:
    _login(client)
    resp = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", b"<testsuites/>", "application/xml")},
        data={"metadata": json.dumps({"project_slug": "nope", "name": "x"})},
    )
    assert resp.status_code == 404
```

Also update `apps/api/tests/conftest.py` to add a `storage_fixture`:
```python
@pytest.fixture
def storage_fixture():
    """In-memory S3 for tests that need a storage instance."""
    import boto3
    from moto import mock_aws
    from prism_api.storage import ObjectStorage

    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="prism")
        yield ObjectStorage(client=client, bucket="prism")
```

(Task 5.3 will add a second fixture that ALSO monkeypatches `runs_module.build_storage` once the router actually calls it.)

- [ ] **Step 2: Run test (FAIL)**

- [ ] **Step 3: Implement router**

`apps/api/src/prism_api/routers/runs.py`:
```python
"""Run upload endpoint."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from prism_api.config import Settings
from prism_api.deps import current_user, get_settings_dep, session_dep
from prism_api.models.run import RunStatus
from prism_api.models.user import User
from prism_api.repos.projects import ProjectRepo
from prism_api.repos.runs import RunRepo
from prism_api.schemas.run import CreateRunMetadata, RunOut, RunTagOut
from prism_api.storage import build_storage
from prism_api.worker.tasks import run_ingest

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


def enqueue_ingest(run_id: str, junit_xml: bytes, archive: bytes | None) -> None:
    """Thin seam so tests can replace the Celery dispatch with an inline call."""
    # Writing upload bodies to storage happens here so the worker can fetch by key.
    # For simplicity in v1 we pass bytes directly via a signed-URL or via a
    # call-site-provided storage. The task signature accepts byte payloads for test
    # friendliness; in production, consider uploading to S3 first and passing keys.
    run_ingest.delay(run_id, junit_xml, archive)  # type: ignore[arg-type]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=RunOut)
async def upload_run(
    junit: UploadFile = File(...),
    metadata: str = Form(...),
    archive: UploadFile | None = File(default=None),
    current: User = Depends(current_user),
    settings: Settings = Depends(get_settings_dep),
    session: Session = Depends(session_dep),
) -> RunOut:
    # 1) Parse metadata JSON
    try:
        meta = CreateRunMetadata.model_validate(json.loads(metadata))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"invalid metadata: {exc}") from exc

    # 2) Resolve project
    project = ProjectRepo(session).get_by_slug(meta.project_slug)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"project '{meta.project_slug}' not found")

    # 3) Create run row
    runs = RunRepo(session)
    run = runs.create(
        project_id=project.id,
        name=meta.name,
        status=RunStatus.PENDING,
        created_by=current.id,
    )
    for k, v in meta.tags.items():
        runs.add_tag(run.id, k, v)
    session.flush()

    # 4) Read payloads
    junit_bytes = await junit.read()
    archive_bytes = await archive.read() if archive is not None else None

    # 5) Run ingest (inline seam for tests; in prod dispatches to Celery worker)
    enqueue_ingest(run.id, junit_bytes, archive_bytes)

    # 6) Respond with the current run state (status may be set by synchronous ingest in tests)
    session.refresh(run)
    tags = runs.tags_for(run.id)
    return RunOut(
        id=run.id,
        project_id=run.project_id,
        name=run.name,
        status=run.status.value,
        started_at=run.started_at,
        finished_at=run.finished_at,
        junit_artifact_id=run.junit_artifact_id,
        tags=[RunTagOut(key=t.key, value=t.value) for t in tags],
    )
```

**Note:** The `enqueue_ingest` function as written passes raw bytes to `run_ingest.delay`. Celery's JSON serializer can't send bytes, so in production you'd upload to S3 first and pass keys. For the walking-skeleton ingest we keep this simple and accept the limitation: tests monkey-patch `enqueue_ingest` inline (see `patch_ingest` fixture), so the production path isn't exercised by tests. Task 5.3 below replaces this with a keys-based enqueue that actually works in prod.

- [ ] **Step 4: Wire the router in main.py**

`apps/api/src/prism_api/main.py` — add import and include:
```python
from prism_api.routers import runs as runs_router
...
app.include_router(runs_router.router)
```

- [ ] **Step 5: Run tests (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_runs_router.py -v
```

- [ ] **Step 6: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(api): POST /api/v1/runs — upload JUnit + archive + metadata"
```

---

### Task 5.3: Keys-based Celery enqueue (production-ready)

Replace `enqueue_ingest` to upload payloads to S3 first and pass keys to Celery.

**Files:**
- Modify: `apps/api/src/prism_api/routers/runs.py`
- Modify: `apps/api/src/prism_api/worker/tasks.py`
- Modify: `apps/api/tests/conftest.py` (simpler `storage_fixture` once enqueue uses keys)

- [ ] **Step 1: Update `enqueue_ingest` to take storage + keys**

Replace `enqueue_ingest` body in `apps/api/src/prism_api/routers/runs.py`:
```python
def enqueue_ingest(
    run_id: str,
    junit_bytes: bytes,
    archive_bytes: bytes | None,
    storage: ObjectStorage,
) -> None:
    junit_key = storage.put_raw(junit_bytes, filename="junit.xml")
    archive_key = storage.put_raw(archive_bytes, filename="archive.zip") if archive_bytes else None
    run_ingest.delay(run_id, junit_key, archive_key)
```

Update the router call site:
```python
storage = build_storage(settings)
storage.ensure_bucket()
enqueue_ingest(run.id, junit_bytes, archive_bytes, storage)
```

Add `from prism_api.storage import ObjectStorage` to the router imports.

- [ ] **Step 2: Update `run_ingest` task to accept keys (already does — no change needed)**

The `run_ingest` task in `apps/api/src/prism_api/worker/tasks.py` already fetches by key. Confirm.

- [ ] **Step 3: Update the test fixture**

In `apps/api/tests/conftest.py`, REPLACE `storage_fixture` with a version that also monkeypatches the router's `build_storage` (so the router uses the in-memory bucket):
```python
@pytest.fixture
def storage_fixture(monkeypatch):
    import boto3
    from moto import mock_aws
    from prism_api.storage import ObjectStorage
    from prism_api.routers import runs as runs_module

    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="prism")
        storage = ObjectStorage(client=client, bucket="prism")
        monkeypatch.setattr(runs_module, "build_storage", lambda s: storage)
        yield storage
```

Then update `patch_ingest` in `apps/api/tests/test_runs_router.py` to match the new 4-arg signature:
```python
@pytest.fixture
def patch_ingest(monkeypatch, db_session, storage_fixture):
    from prism_api.routers import runs as runs_module
    from prism_api.ingest import IngestInputs, ingest_run

    def fake_enqueue(run_id, junit_bytes, archive_bytes, storage):
        ingest_run(
            IngestInputs(run_id=run_id, junit_xml=junit_bytes, archive=archive_bytes),
            session=db_session,
            storage=storage,
        )
        db_session.commit()

    monkeypatch.setattr(runs_module, "enqueue_ingest", fake_enqueue)
```

- [ ] **Step 4: Run tests (PASS)**

- [ ] **Step 5: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(api): enqueue ingest via S3 keys (safe for Celery JSON serializer)"
```

---

## Phase 6: Docker-compose worker service

### Task 6.1: Add worker service to compose

**Files:**
- Modify: `deploy/docker-compose.yml` (add `worker` service)
- Modify: `deploy/docker-compose.dev.yml` (hot reload for worker src)

- [ ] **Step 1: Add worker service in base compose**

Append under `services:` in `deploy/docker-compose.yml`:
```yaml
  worker:
    build:
      context: ../apps/api
      dockerfile: Dockerfile
    restart: unless-stopped
    depends_on:
      postgres: { condition: service_healthy }
      minio:    { condition: service_healthy }
      redis:    { condition: service_healthy }
    environment:
      PRISM_DATABASE_URL: postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      PRISM_S3_ENDPOINT: http://minio:9000
      PRISM_S3_ACCESS_KEY: ${MINIO_ROOT_USER}
      PRISM_S3_SECRET_KEY: ${MINIO_ROOT_PASSWORD}
      PRISM_S3_BUCKET: prism
      PRISM_REDIS_URL: redis://redis:6379/0
      PRISM_JWT_SECRET: ${JWT_SECRET}
    entrypoint: []
    command: ["celery", "-A", "prism_api.worker.celery_app", "worker", "--loglevel=INFO", "--concurrency=2"]
```

Note: `entrypoint: []` overrides the image's `./docker-entrypoint.sh` (which is api-specific — runs alembic, bootstrap-admin). The worker doesn't need those.

- [ ] **Step 2: Add worker overrides in dev**

Append to `deploy/docker-compose.dev.yml` under `services:`:
```yaml
  worker:
    build:
      dockerfile: Dockerfile.dev
    volumes:
      - ../apps/api/src:/app/src
    # Hot reload is manual; restart worker on src change during dev if needed
```

- [ ] **Step 3: Smoke check compose config**

```bash
cd /home/tcollins/dev/prism && docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml --env-file deploy/.env config > /dev/null && echo OK
```
Expected: `OK`.

- [ ] **Step 4: Bring the stack up and confirm worker runs**

```bash
cd /home/tcollins/dev/prism && docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml --env-file deploy/.env up -d --build worker
docker logs prism-worker-1 2>&1 | tail -10
```
Expected: Celery banner with `celery@<hostname>` and `Connected to redis://redis:6379/0`.

- [ ] **Step 5: Commit**

```bash
cd /home/tcollins/dev/prism && git add deploy/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(deploy): add Celery worker service"
```

---

### Task 6.2: End-to-end smoke test via docker

Manual — no commit.

- [ ] **Step 1: Rebuild and launch**

```bash
cd /home/tcollins/dev/prism && docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml --env-file deploy/.env down && docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml --env-file deploy/.env up -d --build
```

- [ ] **Step 2: Log in and create a project**

```bash
curl -s -c /tmp/pc.txt -H 'Content-Type: application/json' -d '{"email":"admin@example.com","password":"change-me-in-prod"}' http://localhost:8000/api/v1/auth/login
curl -s -b /tmp/pc.txt -H 'Content-Type: application/json' -d '{"slug":"audio","name":"Audio"}' http://localhost:8000/api/v1/projects
```

- [ ] **Step 3: Upload a run**

```bash
curl -s -b /tmp/pc.txt \
  -F 'junit=@apps/api/tests/fixtures/sample-junit.xml;type=application/xml' \
  -F 'metadata={"project_slug":"audio","name":"smoke-1","tags":{"branch":"main"}}' \
  http://localhost:8000/api/v1/runs
```
Expected: JSON with `"status": "pending"` (worker processes async; status becomes `mixed` within seconds).

- [ ] **Step 4: Query the database to verify**

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml --env-file deploy/.env exec postgres psql -U prism -d prism -c "SELECT name,status FROM test_runs; SELECT name,pass_count,fail_count FROM test_suites;"
```

---

## What's next (Plan 3 — Browsing & DSP)

After this plan, data exists but is invisible. Plan 3 will add:

- `GET /runs`, `GET /runs/{id}`, `GET /runs/{id}/suites/{id}/cases`, `GET /cases/{id}`
- `GET /artifacts/{id}/download` (presigned redirect), `GET /artifacts/{id}/waveform?downsample=N`
- `GET /artifacts/{id}/fft?window=&nfft=&overlap=` with Welch's method + `DerivedArtifact` cache
- Dashboard UI (run browser) + run detail UI (test tree + plot tabs: time domain / FFT)
- Waveform parsers for CSV, NPY, HDF5 (keyed off `Artifact.kind`)
- Address leftover review items: I5 (AuthProvider error discrimination), CSRF token for upload, web Dockerfile `npm ci`
