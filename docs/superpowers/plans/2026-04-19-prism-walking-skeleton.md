# Prism — Walking Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a deployable Prism stack — `docker compose up` brings the full skeleton online (postgres + minio + redis + api + web), a bootstrap admin can log in via the web UI, and projects can be created and listed. No test data ingest yet — that comes in Plan 2.

**Architecture:** Monorepo with `apps/api` (FastAPI + SQLAlchemy + Alembic) and `apps/web` (React + Vite + Chakra UI v3). All services orchestrated by `deploy/docker-compose.yml`. Tests run on every commit via GitHub Actions.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, pydantic-settings, passlib[bcrypt], python-jose, pytest, ruff, mypy. React 18, Vite 5, TypeScript, Chakra UI v3, TanStack Query v5, react-router 6, axios, vitest, eslint, prettier. PostgreSQL 16, MinIO, Redis 7, nginx (later plans).

---

## Conventions used in this plan

- All file paths are relative to the repo root `/home/tcollins/dev/prism`.
- Bash commands shown should be run from the repo root unless otherwise noted.
- Each task ends with a commit. Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/).
- Tests come before implementation (TDD) for all logic-bearing code; pure scaffolding commits skip the test step but include a smoke check.
- The plan assumes the engineer already has `docker`, `docker compose`, `python 3.12`, `node 20+`, `git` installed.

---

## Phase 0: Repo bootstrap

### Task 0.1: Top-level repo files

**Files:**
- Create: `README.md`
- Create: `Makefile`
- Modify: `.gitignore`

- [ ] **Step 1: Write the README skeleton**

`README.md`:
```markdown
# Prism

A self-hostable web app for managing, browsing, plotting, and cross-analyzing test results — JUnit XML plus measurement artifacts (waveforms, FFTs, logs).

## Quickstart

```bash
cp deploy/.env.example deploy/.env
make up
open http://localhost:8080
```

Default admin login is set in `deploy/.env`. See `docs/getting-started.md` once docs are built.

## Repo layout

- `apps/api/` — FastAPI backend + Celery worker
- `apps/web/` — React frontend (Chakra UI v3)
- `deploy/` — docker-compose orchestration
- `docs/` — MkDocs Material site
```

- [ ] **Step 2: Write the Makefile**

`Makefile`:
```makefile
.PHONY: up down logs build test lint fmt docs clean

COMPOSE := docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml --env-file deploy/.env

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

build:
	$(COMPOSE) build

test: test-api test-web

test-api:
	cd apps/api && uv run pytest

test-web:
	cd apps/web && npm test

lint:
	cd apps/api && uv run ruff check . && uv run mypy src
	cd apps/web && npm run lint

fmt:
	cd apps/api && uv run ruff format .
	cd apps/web && npm run fmt

docs:
	cd docs && mkdocs serve

clean:
	$(COMPOSE) down -v
```

- [ ] **Step 3: Extend .gitignore**

`.gitignore`:
```
.superpowers/

# Python
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
.venv/
*.egg-info/
dist/
build/

# Node
node_modules/
.vite/
coverage/
playwright-report/
test-results/

# Editors
.vscode/
.idea/
*.swp
.DS_Store

# Local env
deploy/.env
.env
.env.local

# Docs build
site/

# Stub recovery file
.stub
```

- [ ] **Step 4: Commit**

```bash
cd /home/tcollins/dev/prism && git add README.md Makefile .gitignore && git commit -m "chore: add README, Makefile, gitignore"
```

---

### Task 0.2: docker-compose skeleton

**Files:**
- Create: `deploy/docker-compose.yml`
- Create: `deploy/docker-compose.dev.yml`
- Create: `deploy/.env.example`

- [ ] **Step 1: Write base docker-compose.yml**

`deploy/docker-compose.yml`:
```yaml
name: prism

services:
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-prism}
      POSTGRES_USER: ${POSTGRES_USER:-prism}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-prism}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER}"]
      interval: 5s
      timeout: 5s
      retries: 10

  minio:
    image: minio/minio:RELEASE.2026-01-15T00-00-00Z
    restart: unless-stopped
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-prism}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-prismprism}
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/ready"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 10

  api:
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
      PRISM_ADMIN_EMAIL: ${ADMIN_EMAIL}
      PRISM_ADMIN_PASSWORD: ${ADMIN_PASSWORD}

  web:
    build:
      context: ../apps/web
      dockerfile: Dockerfile
    restart: unless-stopped
    depends_on: [api]
    ports:
      - "8080:80"

volumes:
  postgres_data:
  minio_data:
```

- [ ] **Step 2: Write dev override**

`deploy/docker-compose.dev.yml`:
```yaml
services:
  postgres:
    ports: ["5432:5432"]

  minio:
    ports:
      - "9000:9000"
      - "9001:9001"

  redis:
    ports: ["6379:6379"]

  api:
    build:
      dockerfile: Dockerfile.dev
    volumes:
      - ../apps/api/src:/app/src
    ports: ["8000:8000"]
    command: ["uvicorn", "prism_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

  web:
    build:
      dockerfile: Dockerfile.dev
    volumes:
      - ../apps/web/src:/app/src
      - ../apps/web/index.html:/app/index.html
    ports: ["8080:5173"]
    command: ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

- [ ] **Step 3: Write .env.example**

`deploy/.env.example`:
```
POSTGRES_DB=prism
POSTGRES_USER=prism
POSTGRES_PASSWORD=change-me-in-prod

MINIO_ROOT_USER=prism
MINIO_ROOT_PASSWORD=change-me-in-prod

JWT_SECRET=replace-with-a-long-random-string

ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=change-me-in-prod
```

- [ ] **Step 4: Smoke check (the api/web images won't build yet — that's fine)**

```bash
cd /home/tcollins/dev/prism && cp deploy/.env.example deploy/.env && \
  docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml --env-file deploy/.env config > /dev/null && echo OK
```
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
cd /home/tcollins/dev/prism && git add deploy/ && git commit -m "chore: add docker-compose skeleton"
```

---

## Phase 1: API project scaffold

### Task 1.1: Python project structure

**Files:**
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/src/prism_api/__init__.py`
- Create: `apps/api/src/prism_api/main.py`
- Create: `apps/api/tests/__init__.py`
- Create: `apps/api/tests/conftest.py`
- Create: `apps/api/Dockerfile`
- Create: `apps/api/Dockerfile.dev`
- Create: `apps/api/.dockerignore`

- [ ] **Step 1: Write pyproject.toml**

`apps/api/pyproject.toml`:
```toml
[project]
name = "prism-api"
version = "0.1.0"
description = "Prism API and Celery worker"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.110",
  "uvicorn[standard]>=0.27",
  "sqlalchemy>=2.0",
  "psycopg[binary]>=3.1",
  "alembic>=1.13",
  "pydantic>=2.6",
  "pydantic-settings>=2.2",
  "python-jose[cryptography]>=3.3",
  "passlib[bcrypt]>=1.7",
  "python-multipart>=0.0.9",
  "boto3>=1.34",
  "celery[redis]>=5.3",
  "junitparser>=3.1",
  "numpy>=1.26",
  "scipy>=1.12",
  "pandas>=2.2",
  "h5py>=3.10",
]

[dependency-groups]
dev = [
  "pytest>=8.0",
  "pytest-asyncio>=0.23",
  "httpx>=0.27",
  "ruff>=0.4",
  "mypy>=1.10",
  "types-passlib",
  "types-python-jose",
  "freezegun>=1.4",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "ASYNC", "S", "C4", "SIM", "RUF"]
ignore = ["S101"]  # asserts ok in tests

[tool.ruff.lint.per-file-ignores]
"tests/**/*" = ["S105", "S106"]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = []
warn_unreachable = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
filterwarnings = ["error"]
```

- [ ] **Step 2: Write package entry point**

`apps/api/src/prism_api/__init__.py`:
```python
"""Prism API package."""

__version__ = "0.1.0"
```

`apps/api/src/prism_api/main.py`:
```python
"""FastAPI app entry point."""
from fastapi import FastAPI

from prism_api import __version__

app = FastAPI(title="Prism API", version=__version__)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "version": __version__}
```

- [ ] **Step 3: Write conftest.py**

`apps/api/tests/__init__.py`: empty file.

`apps/api/tests/conftest.py`:
```python
"""Shared test fixtures."""
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from prism_api.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c
```

- [ ] **Step 4: Write Dockerfiles**

`apps/api/Dockerfile`:
```dockerfile
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN pip install uv
WORKDIR /app
COPY pyproject.toml ./
RUN uv pip install --system --no-cache .
COPY src ./src
EXPOSE 8000
CMD ["uvicorn", "prism_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`apps/api/Dockerfile.dev`:
```dockerfile
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN pip install uv
WORKDIR /app
COPY pyproject.toml ./
RUN uv pip install --system --no-cache --group dev .
COPY src ./src
EXPOSE 8000
```

`apps/api/.dockerignore`:
```
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
tests/
.venv/
```

- [ ] **Step 5: Smoke test the import**

```bash
cd /home/tcollins/dev/prism/apps/api && python -c "import sys; sys.path.insert(0, 'src'); from prism_api.main import app; print(app.title)"
```
Expected output: `Prism API`

- [ ] **Step 6: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git commit -m "feat(api): scaffold FastAPI app with health endpoint"
```

---

### Task 1.2: First passing test (health endpoint)

**Files:**
- Create: `apps/api/tests/test_health.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_health.py`:
```python
"""Health endpoint smoke tests."""
from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
```

- [ ] **Step 2: Run the test (it should pass — endpoint already exists)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_health.py -v
```
Expected: `test_health_returns_ok PASSED`.

If `uv run` is not available, use `python -m pytest tests/test_health.py -v` after `pip install -e .[dev]` from `apps/api/`.

- [ ] **Step 3: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/tests/ && git commit -m "test(api): cover health endpoint"
```

---

## Phase 2: Configuration & database foundation

### Task 2.1: Settings module

**Files:**
- Create: `apps/api/src/prism_api/config.py`
- Create: `apps/api/tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_config.py`:
```python
"""Settings loading tests."""
import pytest

from prism_api.config import Settings


def test_settings_load_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISM_DATABASE_URL", "postgresql+psycopg://x:y@db:5432/z")
    monkeypatch.setenv("PRISM_S3_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("PRISM_S3_ACCESS_KEY", "ak")
    monkeypatch.setenv("PRISM_S3_SECRET_KEY", "sk")
    monkeypatch.setenv("PRISM_S3_BUCKET", "prism")
    monkeypatch.setenv("PRISM_REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("PRISM_JWT_SECRET", "topsecret")
    s = Settings()
    assert s.database_url.startswith("postgresql+psycopg://")
    assert s.s3_bucket == "prism"
    assert s.jwt_secret == "topsecret"


def test_settings_admin_bootstrap_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISM_DATABASE_URL", "postgresql+psycopg://x:y@db:5432/z")
    monkeypatch.setenv("PRISM_S3_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("PRISM_S3_ACCESS_KEY", "ak")
    monkeypatch.setenv("PRISM_S3_SECRET_KEY", "sk")
    monkeypatch.setenv("PRISM_S3_BUCKET", "prism")
    monkeypatch.setenv("PRISM_REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("PRISM_JWT_SECRET", "topsecret")
    monkeypatch.delenv("PRISM_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("PRISM_ADMIN_PASSWORD", raising=False)
    s = Settings()
    assert s.admin_email is None
    assert s.admin_password is None
```

- [ ] **Step 2: Run the test (FAIL: module not found)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_config.py -v
```
Expected: `ModuleNotFoundError: No module named 'prism_api.config'`.

- [ ] **Step 3: Write the implementation**

`apps/api/src/prism_api/config.py`:
```python
"""App configuration via pydantic-settings."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings. All vars prefixed with PRISM_."""

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
    admin_email: str | None = None
    admin_password: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

- [ ] **Step 4: Run the test (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_config.py -v
```
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git commit -m "feat(api): add Settings module"
```

---

### Task 2.2: Database session & Base model

**Files:**
- Create: `apps/api/src/prism_api/db.py`
- Create: `apps/api/src/prism_api/models/__init__.py`
- Create: `apps/api/src/prism_api/models/base.py`
- Create: `apps/api/tests/test_db.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_db.py`:
```python
"""Database engine + session smoke tests (uses SQLite in-memory)."""
from sqlalchemy import text

from prism_api.db import build_engine, build_session_factory


def test_engine_round_trip() -> None:
    engine = build_engine("sqlite:///:memory:")
    session_factory = build_session_factory(engine)
    with session_factory() as session:
        result = session.execute(text("SELECT 1")).scalar_one()
        assert result == 1
```

- [ ] **Step 2: Run test (FAIL — module missing)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_db.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write the Base + db module**

`apps/api/src/prism_api/models/__init__.py`:
```python
"""SQLAlchemy models."""
from prism_api.models.base import Base

__all__ = ["Base"]
```

`apps/api/src/prism_api/models/base.py`:
```python
"""Declarative SQLAlchemy Base + common mixins."""
from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Project-wide declarative base."""


class TimestampMixin:
    """Mixin providing created_at / updated_at."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
```

`apps/api/src/prism_api/db.py`:
```python
"""Database engine and session factory."""
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from prism_api.config import get_settings


def build_engine(url: str | None = None) -> Engine:
    return create_engine(url or get_settings().database_url, pool_pre_ping=True, future=True)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _factory() -> sessionmaker[Session]:
    global _engine, _session_factory
    if _session_factory is None:
        _engine = build_engine()
        _session_factory = build_session_factory(_engine)
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    session = _factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with session_scope() as session:
        yield session
```

- [ ] **Step 4: Run test (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_db.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git commit -m "feat(api): add SQLAlchemy Base, engine, session factory"
```

---

### Task 2.3: User & Project models

**Files:**
- Create: `apps/api/src/prism_api/models/user.py`
- Create: `apps/api/src/prism_api/models/project.py`
- Create: `apps/api/tests/test_models_smoke.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_models_smoke.py`:
```python
"""Model smoke tests against in-memory SQLite."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from prism_api.models import Base
from prism_api.models.project import Project
from prism_api.models.user import User


def test_create_user_and_project() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        user = User(email="a@b.com", password_hash="x")
        project = Project(slug="audio", name="Audio Codec", description="d")
        session.add_all([user, project])
        session.commit()
        assert user.id is not None
        assert project.id is not None
        assert project.slug == "audio"
```

- [ ] **Step 2: Run test (FAIL)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_models_smoke.py -v
```
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement User and Project models**

`apps/api/src/prism_api/models/user.py`:
```python
"""User model."""
import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from prism_api.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
```

`apps/api/src/prism_api/models/project.py`:
```python
"""Project model."""
import uuid

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from prism_api.models.base import Base, TimestampMixin


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
```

Update `apps/api/src/prism_api/models/__init__.py`:
```python
"""SQLAlchemy models."""
from prism_api.models.base import Base
from prism_api.models.project import Project
from prism_api.models.user import User

__all__ = ["Base", "Project", "User"]
```

- [ ] **Step 4: Run test (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_models_smoke.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git commit -m "feat(api): add User and Project models"
```

---

### Task 2.4: Alembic setup & initial migration

**Files:**
- Create: `apps/api/alembic.ini`
- Create: `apps/api/src/prism_api/migrations/env.py`
- Create: `apps/api/src/prism_api/migrations/script.py.mako`
- Create: `apps/api/src/prism_api/migrations/versions/0001_initial.py`

- [ ] **Step 1: Write alembic.ini**

`apps/api/alembic.ini`:
```ini
[alembic]
script_location = src/prism_api/migrations
prepend_sys_path = src
version_path_separator = os

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: Write env.py**

`apps/api/src/prism_api/migrations/env.py`:
```python
"""Alembic environment."""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from prism_api.config import get_settings
from prism_api.models import Base
import prism_api.models  # noqa: F401  ensure all models registered

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3: Write script template**

`apps/api/src/prism_api/migrations/script.py.mako`:
```python
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 4: Write initial migration**

`apps/api/src/prism_api/migrations/versions/0001_initial.py`:
```python
"""initial schema: users + projects

Revision ID: 0001
Revises:
Create Date: 2026-04-19
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slug", name="uq_projects_slug"),
    )
    op.create_index("ix_projects_slug", "projects", ["slug"])


def downgrade() -> None:
    op.drop_index("ix_projects_slug", table_name="projects")
    op.drop_table("projects")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
```

- [ ] **Step 5: Add alembic to dependency-groups.dev (if not already)**

Edit `apps/api/pyproject.toml` dev group to add `"alembic>=1.13"` if missing (it should already be in main `dependencies`).

- [ ] **Step 6: Smoke test against SQLite**

```bash
cd /home/tcollins/dev/prism/apps/api && PRISM_DATABASE_URL=sqlite:///./test.db PRISM_S3_ENDPOINT=x PRISM_S3_ACCESS_KEY=x PRISM_S3_SECRET_KEY=x PRISM_S3_BUCKET=x PRISM_REDIS_URL=x PRISM_JWT_SECRET=x uv run alembic upgrade head && rm -f test.db
```
Expected: `Running upgrade  -> 0001` then no errors.

- [ ] **Step 7: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git commit -m "feat(api): add Alembic and initial migration"
```

---

## Phase 3: Auth

### Task 3.1: Password hashing helpers

**Files:**
- Create: `apps/api/src/prism_api/auth.py`
- Create: `apps/api/tests/test_auth.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_auth.py`:
```python
"""Auth helpers."""
from datetime import timedelta

import pytest

from prism_api.auth import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password() -> None:
    h = hash_password("hunter2")
    assert h != "hunter2"
    assert verify_password("hunter2", h)
    assert not verify_password("wrong", h)


def test_create_and_decode_token() -> None:
    token = create_access_token(subject="user-id-123", secret="s", ttl=timedelta(minutes=10))
    claims = decode_access_token(token, secret="s")
    assert claims.subject == "user-id-123"


def test_decode_rejects_bad_signature() -> None:
    token = create_access_token(subject="u", secret="s1", ttl=timedelta(minutes=10))
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, secret="s2")


def test_decode_rejects_expired_token() -> None:
    token = create_access_token(subject="u", secret="s", ttl=timedelta(seconds=-1))
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, secret="s")
```

- [ ] **Step 2: Run test (FAIL)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_auth.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement auth helpers**

`apps/api/src/prism_api/auth.py`:
```python
"""Password hashing and JWT helpers."""
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


class InvalidTokenError(Exception):
    """Raised when a JWT cannot be decoded or is expired."""


@dataclass(frozen=True)
class TokenClaims:
    subject: str
    expires_at: datetime


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


def create_access_token(*, subject: str, secret: str, ttl: timedelta, algorithm: str = "HS256") -> str:
    expires_at = datetime.now(UTC) + ttl
    payload = {"sub": subject, "exp": int(expires_at.timestamp())}
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_access_token(token: str, *, secret: str, algorithm: str = "HS256") -> TokenClaims:
    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
    except JWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
    sub = payload.get("sub")
    exp = payload.get("exp")
    if not isinstance(sub, str) or not isinstance(exp, int):
        raise InvalidTokenError("malformed claims")
    return TokenClaims(subject=sub, expires_at=datetime.fromtimestamp(exp, tz=UTC))
```

- [ ] **Step 4: Run tests (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_auth.py -v
```
Expected: 4/4 PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git commit -m "feat(api): password hashing and JWT helpers"
```

---

### Task 3.2: User repository (CRUD on User model)

**Files:**
- Create: `apps/api/src/prism_api/repos/__init__.py`
- Create: `apps/api/src/prism_api/repos/users.py`
- Create: `apps/api/tests/test_user_repo.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_user_repo.py`:
```python
"""User repository tests against in-memory SQLite."""
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from prism_api.models import Base
from prism_api.repos.users import UserRepo


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        yield s


def test_create_and_lookup(session: Session) -> None:
    repo = UserRepo(session)
    user = repo.create(email="a@b.com", password_hash="h")
    session.commit()
    assert repo.get_by_email("a@b.com") == user
    assert repo.get_by_id(user.id) == user


def test_list_users(session: Session) -> None:
    repo = UserRepo(session)
    repo.create(email="a@b.com", password_hash="h")
    repo.create(email="c@d.com", password_hash="h")
    session.commit()
    users = repo.list_all()
    assert {u.email for u in users} == {"a@b.com", "c@d.com"}


def test_delete_user(session: Session) -> None:
    repo = UserRepo(session)
    user = repo.create(email="a@b.com", password_hash="h")
    session.commit()
    repo.delete(user.id)
    session.commit()
    assert repo.get_by_id(user.id) is None
```

- [ ] **Step 2: Run test (FAIL)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_user_repo.py -v
```
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement the repo**

`apps/api/src/prism_api/repos/__init__.py`: empty file.

`apps/api/src/prism_api/repos/users.py`:
```python
"""User repository."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from prism_api.models.user import User


class UserRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, email: str, password_hash: str) -> User:
        user = User(email=email, password_hash=password_hash)
        self._session.add(user)
        self._session.flush()
        return user

    def get_by_id(self, user_id: str) -> User | None:
        return self._session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self._session.execute(select(User).where(User.email == email)).scalar_one_or_none()

    def list_all(self) -> list[User]:
        return list(self._session.execute(select(User).order_by(User.created_at)).scalars())

    def delete(self, user_id: str) -> None:
        user = self._session.get(User, user_id)
        if user is not None:
            self._session.delete(user)
```

- [ ] **Step 4: Run tests (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_user_repo.py -v
```
Expected: 3/3 PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git commit -m "feat(api): UserRepo with CRUD"
```

---

### Task 3.3: Bootstrap admin on startup

**Files:**
- Create: `apps/api/src/prism_api/bootstrap.py`
- Create: `apps/api/tests/test_bootstrap.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_bootstrap.py`:
```python
"""Bootstrap admin user tests."""
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from prism_api.bootstrap import ensure_bootstrap_admin
from prism_api.models import Base
from prism_api.repos.users import UserRepo


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        yield s


def test_creates_admin_on_empty_db(session: Session) -> None:
    ensure_bootstrap_admin(session, email="admin@x.com", password="p")
    session.commit()
    assert UserRepo(session).get_by_email("admin@x.com") is not None


def test_skipped_when_users_already_exist(session: Session) -> None:
    UserRepo(session).create(email="existing@x.com", password_hash="h")
    session.commit()
    ensure_bootstrap_admin(session, email="admin@x.com", password="p")
    session.commit()
    assert UserRepo(session).get_by_email("admin@x.com") is None


def test_skipped_when_creds_missing(session: Session) -> None:
    ensure_bootstrap_admin(session, email=None, password=None)
    session.commit()
    assert UserRepo(session).list_all() == []
```

- [ ] **Step 2: Run test (FAIL)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_bootstrap.py -v
```
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement bootstrap**

`apps/api/src/prism_api/bootstrap.py`:
```python
"""Bootstrap helpers — runs on app startup."""
from sqlalchemy.orm import Session

from prism_api.auth import hash_password
from prism_api.repos.users import UserRepo


def ensure_bootstrap_admin(session: Session, *, email: str | None, password: str | None) -> None:
    """Create the bootstrap admin if no users exist and credentials are provided."""
    if not email or not password:
        return
    repo = UserRepo(session)
    if repo.list_all():
        return
    repo.create(email=email, password_hash=hash_password(password))
```

- [ ] **Step 4: Run tests (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_bootstrap.py -v
```
Expected: 3/3 PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git commit -m "feat(api): bootstrap admin on first start"
```

---

### Task 3.4: Auth schemas & router (login + me)

**Files:**
- Create: `apps/api/src/prism_api/schemas/__init__.py`
- Create: `apps/api/src/prism_api/schemas/auth.py`
- Create: `apps/api/src/prism_api/routers/__init__.py`
- Create: `apps/api/src/prism_api/routers/auth.py`
- Create: `apps/api/src/prism_api/deps.py`
- Create: `apps/api/tests/test_auth_router.py`
- Modify: `apps/api/src/prism_api/main.py`
- Modify: `apps/api/tests/conftest.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_auth_router.py`:
```python
"""Auth router integration tests."""
from fastapi.testclient import TestClient


def test_login_then_me(client: TestClient, seed_admin: None) -> None:
    r = client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    assert r.status_code == 200
    assert r.cookies.get("prism_session") is not None

    r2 = client.get("/api/v1/auth/me")
    assert r2.status_code == 200
    assert r2.json()["email"] == "admin@x.com"


def test_login_wrong_password(client: TestClient, seed_admin: None) -> None:
    r = client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "nope"})
    assert r.status_code == 401


def test_me_unauthenticated(client: TestClient) -> None:
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_logout_clears_cookie(client: TestClient, seed_admin: None) -> None:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    r = client.post("/api/v1/auth/logout")
    assert r.status_code == 204
    r2 = client.get("/api/v1/auth/me")
    assert r2.status_code == 401
```

- [ ] **Step 2: Update conftest.py with shared DB fixture**

`apps/api/tests/conftest.py`:
```python
"""Shared test fixtures."""
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from prism_api.auth import hash_password
from prism_api.config import Settings
from prism_api.deps import get_settings_dep, session_dep
from prism_api.main import app
from prism_api.models import Base
from prism_api.repos.users import UserRepo


@pytest.fixture
def settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        database_url="sqlite:///:memory:",
        s3_endpoint="x",
        s3_access_key="x",
        s3_secret_key="x",
        s3_bucket="x",
        redis_url="x",
        jwt_secret="testsecret",
    )


@pytest.fixture
def db_session(settings: Settings) -> Iterator[Session]:
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    Session_ = sessionmaker(bind=engine)
    with Session_() as session:
        yield session


@pytest.fixture
def client(settings: Settings, db_session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_settings_dep] = lambda: settings
    app.dependency_overrides[session_dep] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def seed_admin(db_session: Session) -> None:
    UserRepo(db_session).create(email="admin@x.com", password_hash=hash_password("pw"))
    db_session.commit()
```

- [ ] **Step 3: Implement deps module**

`apps/api/src/prism_api/deps.py`:
```python
"""FastAPI dependencies."""
from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from prism_api.auth import InvalidTokenError, decode_access_token
from prism_api.config import Settings, get_settings
from prism_api.db import session_scope
from prism_api.models.user import User
from prism_api.repos.users import UserRepo

SESSION_COOKIE = "prism_session"


def get_settings_dep() -> Settings:
    return get_settings()


def session_dep() -> Iterator[Session]:
    with session_scope() as s:
        yield s


def current_user(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
    session: Session = Depends(session_dep),
) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing session")
    try:
        claims = decode_access_token(token, secret=settings.jwt_secret, algorithm=settings.jwt_algorithm)
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    user = UserRepo(session).get_by_id(claims.subject)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user no longer exists")
    return user
```

- [ ] **Step 4: Implement auth schemas**

`apps/api/src/prism_api/schemas/__init__.py`: empty.

`apps/api/src/prism_api/schemas/auth.py`:
```python
"""Auth request/response schemas."""
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: EmailStr
```

- [ ] **Step 5: Implement auth router**

`apps/api/src/prism_api/routers/__init__.py`: empty.

`apps/api/src/prism_api/routers/auth.py`:
```python
"""Auth endpoints."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from prism_api.auth import create_access_token, verify_password
from prism_api.config import Settings
from prism_api.deps import SESSION_COOKIE, current_user, get_settings_dep, session_dep
from prism_api.models.user import User
from prism_api.repos.users import UserRepo
from prism_api.schemas.auth import LoginRequest, UserOut

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login")
def login(
    body: LoginRequest,
    response: Response,
    settings: Settings = Depends(get_settings_dep),
    session: Session = Depends(session_dep),
) -> UserOut:
    user = UserRepo(session).get_by_email(body.email)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    token = create_access_token(
        subject=user.id,
        secret=settings.jwt_secret,
        ttl=timedelta(minutes=settings.jwt_ttl_minutes),
        algorithm=settings.jwt_algorithm,
    )
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # dev; prod nginx terminates TLS
        max_age=settings.jwt_ttl_minutes * 60,
        path="/",
    )
    return UserOut(id=user.id, email=user.email)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/me")
def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut(id=user.id, email=user.email)
```

- [ ] **Step 6: Wire router into main.py**

`apps/api/src/prism_api/main.py`:
```python
"""FastAPI app entry point."""
from fastapi import FastAPI

from prism_api import __version__
from prism_api.routers import auth as auth_router

app = FastAPI(title="Prism API", version=__version__)
app.include_router(auth_router.router)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
```

- [ ] **Step 7: Run tests (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_auth_router.py -v
```
Expected: 4/4 PASS.

- [ ] **Step 8: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git commit -m "feat(api): auth endpoints (login/logout/me) with JWT cookie"
```

---

### Task 3.5: Users router (list / create / delete)

**Files:**
- Create: `apps/api/src/prism_api/schemas/user.py`
- Create: `apps/api/src/prism_api/routers/users.py`
- Create: `apps/api/tests/test_users_router.py`
- Modify: `apps/api/src/prism_api/main.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_users_router.py`:
```python
"""Users router tests."""
from fastapi.testclient import TestClient


def _login(client: TestClient, email: str = "admin@x.com", password: str = "pw") -> None:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200


def test_list_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/users").status_code == 401


def test_create_and_list(client: TestClient, seed_admin: None) -> None:
    _login(client)
    r = client.post(
        "/api/v1/users",
        json={"email": "newbie@x.com", "password": "anotherpw"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "newbie@x.com"

    listing = client.get("/api/v1/users").json()
    assert {u["email"] for u in listing} == {"admin@x.com", "newbie@x.com"}


def test_create_duplicate_email(client: TestClient, seed_admin: None) -> None:
    _login(client)
    r = client.post(
        "/api/v1/users",
        json={"email": "admin@x.com", "password": "pw2"},
    )
    assert r.status_code == 409


def test_delete_user(client: TestClient, seed_admin: None) -> None:
    _login(client)
    new = client.post(
        "/api/v1/users",
        json={"email": "victim@x.com", "password": "pw"},
    ).json()
    r = client.delete(f"/api/v1/users/{new['id']}")
    assert r.status_code == 204
    assert {u["email"] for u in client.get("/api/v1/users").json()} == {"admin@x.com"}
```

- [ ] **Step 2: Run tests (FAIL)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_users_router.py -v
```
Expected: 404s and import errors.

- [ ] **Step 3: Implement schemas**

`apps/api/src/prism_api/schemas/user.py`:
```python
"""User request/response schemas."""
from pydantic import BaseModel, EmailStr, Field


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class UserOut(BaseModel):
    id: str
    email: EmailStr
```

- [ ] **Step 4: Implement router**

`apps/api/src/prism_api/routers/users.py`:
```python
"""User management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from prism_api.auth import hash_password
from prism_api.deps import current_user, session_dep
from prism_api.models.user import User
from prism_api.repos.users import UserRepo
from prism_api.schemas.user import CreateUserRequest, UserOut

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("")
def list_users(
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[UserOut]:
    return [UserOut(id=u.id, email=u.email) for u in UserRepo(session).list_all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    body: CreateUserRequest,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> UserOut:
    try:
        user = UserRepo(session).create(
            email=body.email, password_hash=hash_password(body.password)
        )
        session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "email already exists") from exc
    return UserOut(id=user.id, email=user.email)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> Response:
    UserRepo(session).delete(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 5: Wire into main.py**

Update `apps/api/src/prism_api/main.py` imports + `app.include_router`:
```python
from prism_api.routers import auth as auth_router, users as users_router
...
app.include_router(auth_router.router)
app.include_router(users_router.router)
```

- [ ] **Step 6: Run tests (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_users_router.py -v
```
Expected: 4/4 PASS.

- [ ] **Step 7: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git commit -m "feat(api): user CRUD endpoints"
```

---

## Phase 4: Projects

### Task 4.1: Project repository

**Files:**
- Create: `apps/api/src/prism_api/repos/projects.py`
- Create: `apps/api/tests/test_project_repo.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_project_repo.py`:
```python
"""Project repository tests."""
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from prism_api.models import Base
from prism_api.repos.projects import ProjectRepo


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        yield s


def test_create_and_lookup(session: Session) -> None:
    repo = ProjectRepo(session)
    p = repo.create(slug="audio", name="Audio", description="hi")
    session.commit()
    assert repo.get_by_slug("audio") == p


def test_list_projects(session: Session) -> None:
    repo = ProjectRepo(session)
    repo.create(slug="a", name="A")
    repo.create(slug="b", name="B")
    session.commit()
    assert [p.slug for p in repo.list_all()] == ["a", "b"]


def test_delete(session: Session) -> None:
    repo = ProjectRepo(session)
    p = repo.create(slug="a", name="A")
    session.commit()
    repo.delete(p.id)
    session.commit()
    assert repo.get_by_slug("a") is None
```

- [ ] **Step 2: Run test (FAIL)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_project_repo.py -v
```

- [ ] **Step 3: Implement ProjectRepo**

`apps/api/src/prism_api/repos/projects.py`:
```python
"""Project repository."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from prism_api.models.project import Project


class ProjectRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, slug: str, name: str, description: str = "") -> Project:
        project = Project(slug=slug, name=name, description=description)
        self._session.add(project)
        self._session.flush()
        return project

    def get_by_slug(self, slug: str) -> Project | None:
        return self._session.execute(
            select(Project).where(Project.slug == slug)
        ).scalar_one_or_none()

    def get_by_id(self, project_id: str) -> Project | None:
        return self._session.get(Project, project_id)

    def list_all(self) -> list[Project]:
        return list(
            self._session.execute(select(Project).order_by(Project.created_at)).scalars()
        )

    def delete(self, project_id: str) -> None:
        proj = self._session.get(Project, project_id)
        if proj is not None:
            self._session.delete(proj)
```

- [ ] **Step 4: Run tests (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_project_repo.py -v
```

- [ ] **Step 5: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git commit -m "feat(api): ProjectRepo with CRUD"
```

---

### Task 4.2: Projects router

**Files:**
- Create: `apps/api/src/prism_api/schemas/project.py`
- Create: `apps/api/src/prism_api/routers/projects.py`
- Create: `apps/api/tests/test_projects_router.py`
- Modify: `apps/api/src/prism_api/main.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_projects_router.py`:
```python
"""Projects router tests."""
from fastapi.testclient import TestClient


def _login(client: TestClient) -> None:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})


def test_create_list_get(client: TestClient, seed_admin: None) -> None:
    _login(client)
    r = client.post(
        "/api/v1/projects",
        json={"slug": "audio-codec", "name": "Audio Codec", "description": "DSP work"},
    )
    assert r.status_code == 201
    listing = client.get("/api/v1/projects").json()
    assert listing[0]["slug"] == "audio-codec"

    detail = client.get("/api/v1/projects/audio-codec").json()
    assert detail["name"] == "Audio Codec"


def test_get_unknown_404(client: TestClient, seed_admin: None) -> None:
    _login(client)
    r = client.get("/api/v1/projects/missing")
    assert r.status_code == 404


def test_create_duplicate_409(client: TestClient, seed_admin: None) -> None:
    _login(client)
    client.post(
        "/api/v1/projects",
        json={"slug": "a", "name": "A"},
    )
    r = client.post("/api/v1/projects", json={"slug": "a", "name": "A2"})
    assert r.status_code == 409


def test_invalid_slug_422(client: TestClient, seed_admin: None) -> None:
    _login(client)
    r = client.post("/api/v1/projects", json={"slug": "Has Spaces", "name": "x"})
    assert r.status_code == 422
```

- [ ] **Step 2: Run tests (FAIL)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_projects_router.py -v
```

- [ ] **Step 3: Implement schemas**

`apps/api/src/prism_api/schemas/project.py`:
```python
"""Project schemas."""
import re

from pydantic import BaseModel, Field, field_validator

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,98}[a-z0-9])?$")


class CreateProjectRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    description: str = ""

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError("slug must be lowercase alphanumeric with internal hyphens")
        return v


class ProjectOut(BaseModel):
    id: str
    slug: str
    name: str
    description: str
```

- [ ] **Step 4: Implement router**

`apps/api/src/prism_api/routers/projects.py`:
```python
"""Project endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from prism_api.deps import current_user, session_dep
from prism_api.models.user import User
from prism_api.repos.projects import ProjectRepo
from prism_api.schemas.project import CreateProjectRequest, ProjectOut

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get("")
def list_projects(
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[ProjectOut]:
    return [
        ProjectOut(id=p.id, slug=p.slug, name=p.name, description=p.description)
        for p in ProjectRepo(session).list_all()
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(
    body: CreateProjectRequest,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> ProjectOut:
    try:
        p = ProjectRepo(session).create(slug=body.slug, name=body.name, description=body.description)
        session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "slug already exists") from exc
    return ProjectOut(id=p.id, slug=p.slug, name=p.name, description=p.description)


@router.get("/{slug}")
def get_project(
    slug: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> ProjectOut:
    p = ProjectRepo(session).get_by_slug(slug)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    return ProjectOut(id=p.id, slug=p.slug, name=p.name, description=p.description)
```

- [ ] **Step 5: Wire into main.py**

```python
from prism_api.routers import auth as auth_router, projects as projects_router, users as users_router
...
app.include_router(projects_router.router)
```

- [ ] **Step 6: Run tests (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_projects_router.py -v
```
Expected: 4/4 PASS.

- [ ] **Step 7: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git commit -m "feat(api): projects CRUD endpoints"
```

---

### Task 4.3: Bootstrap CLI + Docker entrypoint

The bootstrap admin is created via an explicit CLI invoked by the container entrypoint *after* migrations. This avoids tangling the FastAPI lifespan with DB writes and makes the bootstrap path easy to test in isolation.

**Files:**
- Create: `apps/api/src/prism_api/cli.py`
- Create: `apps/api/docker-entrypoint.sh`
- Create: `apps/api/tests/test_cli.py`
- Modify: `apps/api/Dockerfile`
- Modify: `apps/api/Dockerfile.dev`
- Modify: `deploy/docker-compose.yml` (api command)

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_cli.py`:
```python
"""CLI bootstrap test."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from prism_api.cli import bootstrap_admin
from prism_api.config import Settings
from prism_api.models import Base
from prism_api.repos.users import UserRepo


@pytest.fixture
def settings(tmp_path) -> Settings:
    db_path = tmp_path / "test.db"
    return Settings(  # type: ignore[call-arg]
        database_url=f"sqlite:///{db_path}",
        s3_endpoint="x",
        s3_access_key="x",
        s3_secret_key="x",
        s3_bucket="x",
        redis_url="x",
        jwt_secret="s",
        admin_email="boot@x.com",
        admin_password="bootpw",
    )


def test_bootstrap_admin_creates_user(settings: Settings) -> None:
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    bootstrap_admin(settings)
    with sessionmaker(bind=engine)() as s:
        assert UserRepo(s).get_by_email("boot@x.com") is not None


def test_bootstrap_admin_idempotent(settings: Settings) -> None:
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    bootstrap_admin(settings)
    bootstrap_admin(settings)  # second call should be a no-op
    with sessionmaker(bind=engine)() as s:
        assert len(UserRepo(s).list_all()) == 1
```

- [ ] **Step 2: Run test (FAIL — module missing)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_cli.py -v
```

- [ ] **Step 3: Implement the CLI**

`apps/api/src/prism_api/cli.py`:
```python
"""Command-line entry points for ops tasks."""
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from prism_api.bootstrap import ensure_bootstrap_admin
from prism_api.config import Settings, get_settings


def bootstrap_admin(settings: Settings | None = None) -> None:
    """Create the bootstrap admin if no users exist and credentials are set."""
    s = settings or get_settings()
    engine = create_engine(s.database_url)
    with sessionmaker(bind=engine)() as session:
        ensure_bootstrap_admin(
            session, email=s.admin_email, password=s.admin_password
        )
        session.commit()


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: prism-api <bootstrap-admin>", file=sys.stderr)
        return 2
    cmd = sys.argv[1]
    if cmd == "bootstrap-admin":
        bootstrap_admin()
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_cli.py -v
```

- [ ] **Step 5: Write the docker entrypoint**

`apps/api/docker-entrypoint.sh`:
```bash
#!/bin/sh
set -e
alembic upgrade head
python -m prism_api.cli bootstrap-admin || true
exec "$@"
```

- [ ] **Step 6: Update Dockerfiles to use the entrypoint**

`apps/api/Dockerfile`:
```dockerfile
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN pip install uv
WORKDIR /app
COPY pyproject.toml ./
RUN uv pip install --system --no-cache .
COPY src ./src
COPY alembic.ini ./
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "prism_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`apps/api/Dockerfile.dev`:
```dockerfile
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN pip install uv
WORKDIR /app
COPY pyproject.toml ./
RUN uv pip install --system --no-cache --group dev .
COPY src ./src
COPY alembic.ini ./
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "prism_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 7: Run all api tests once more (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest -v
```
Expected: all green.

- [ ] **Step 8: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git commit -m "feat(api): bootstrap-admin CLI + docker entrypoint runs migrations and bootstrap"
```

---

## Phase 5: Web project scaffold

### Task 5.1: Vite + React + Chakra scaffold

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/tsconfig.node.json`
- Create: `apps/web/vite.config.ts`
- Create: `apps/web/index.html`
- Create: `apps/web/src/main.tsx`
- Create: `apps/web/src/App.tsx`
- Create: `apps/web/src/theme.ts`
- Create: `apps/web/Dockerfile`
- Create: `apps/web/Dockerfile.dev`
- Create: `apps/web/nginx.conf`
- Create: `apps/web/.dockerignore`
- Create: `apps/web/eslint.config.js`
- Create: `apps/web/prettier.config.js`
- Create: `apps/web/vitest.config.ts`
- Create: `apps/web/.gitignore`

- [ ] **Step 1: Write package.json**

`apps/web/package.json`:
```json
{
  "name": "prism-web",
  "private": true,
  "type": "module",
  "version": "0.1.0",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview --port 8080 --host",
    "lint": "eslint . --max-warnings 0",
    "fmt": "prettier --write .",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "@chakra-ui/react": "^3.2.0",
    "@emotion/react": "^11.11.4",
    "@tanstack/react-query": "^5.40.0",
    "axios": "^1.7.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-hook-form": "^7.52.0",
    "react-router-dom": "^6.24.0",
    "zod": "^3.23.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.0",
    "@testing-library/react": "^16.0.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@typescript-eslint/eslint-plugin": "^7.13.0",
    "@typescript-eslint/parser": "^7.13.0",
    "@vitejs/plugin-react": "^4.3.0",
    "eslint": "^9.5.0",
    "eslint-plugin-react-hooks": "^4.6.0",
    "eslint-plugin-react-refresh": "^0.4.0",
    "jsdom": "^24.1.0",
    "prettier": "^3.3.0",
    "typescript": "^5.5.0",
    "vite": "^5.3.0",
    "vitest": "^2.0.0"
  }
}
```

- [ ] **Step 2: Write tsconfig and vite config**

`apps/web/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2023", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "isolatedModules": true,
    "verbatimModuleSyntax": false,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "tests"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

`apps/web/tsconfig.node.json`:
```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts", "vitest.config.ts"]
}
```

`apps/web/vite.config.ts`:
```ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL ?? 'http://api:8000',
        changeOrigin: true,
      },
    },
  },
});
```

`apps/web/vitest.config.ts`:
```ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
  },
});
```

- [ ] **Step 3: Write index.html and React entrypoints**

`apps/web/index.html`:
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Prism</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`apps/web/src/main.tsx`:
```tsx
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

import { App } from './App';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ChakraProvider value={defaultSystem}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </ChakraProvider>
  </StrictMode>,
);
```

`apps/web/src/App.tsx`:
```tsx
import { Heading } from '@chakra-ui/react';

export function App() {
  return <Heading p={6}>Prism</Heading>;
}
```

`apps/web/src/theme.ts`:
```ts
import { createSystem, defaultConfig } from '@chakra-ui/react';

export const system = createSystem(defaultConfig, {
  globalCss: {
    'html, body': { backgroundColor: '#0f1419', color: '#e2e8f0' },
  },
});
```

- [ ] **Step 4: Write Dockerfiles**

`apps/web/Dockerfile`:
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json ./
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
```

`apps/web/Dockerfile.dev`:
```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package.json ./
RUN npm install --no-audit --no-fund
COPY . .
EXPOSE 5173
```

`apps/web/nginx.conf`:
```
server {
  listen 80;
  server_name _;
  root /usr/share/nginx/html;
  index index.html;

  location /api/ {
    proxy_pass http://api:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  }

  location / {
    try_files $uri /index.html;
  }
}
```

`apps/web/.dockerignore`:
```
node_modules
dist
coverage
playwright-report
test-results
```

- [ ] **Step 5: Write eslint, prettier, gitignore**

`apps/web/eslint.config.js`:
```js
import js from '@eslint/js';
import tsParser from '@typescript-eslint/parser';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';

export default [
  js.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: { parser: tsParser, ecmaVersion: 'latest', sourceType: 'module' },
    plugins: { '@typescript-eslint': tsPlugin, 'react-hooks': reactHooks, 'react-refresh': reactRefresh },
    rules: {
      ...tsPlugin.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': 'warn',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    },
  },
  { ignores: ['dist', 'node_modules', 'coverage'] },
];
```

`apps/web/prettier.config.js`:
```js
export default {
  semi: true,
  singleQuote: true,
  trailingComma: 'all',
  printWidth: 100,
};
```

`apps/web/.gitignore`:
```
node_modules
dist
coverage
.vite
playwright-report
test-results
```

- [ ] **Step 6: Smoke test build (after `npm install`)**

```bash
cd /home/tcollins/dev/prism/apps/web && npm install --no-audit --no-fund && npm run build
```
Expected: `dist/` built successfully.

- [ ] **Step 7: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/web/ && git commit -m "feat(web): scaffold Vite + React + Chakra UI v3"
```

---

### Task 5.2: First passing component test

**Files:**
- Create: `apps/web/tests/setup.ts`
- Create: `apps/web/tests/App.test.tsx`

- [ ] **Step 1: Write test setup**

`apps/web/tests/setup.ts`:
```ts
import '@testing-library/jest-dom';
```

- [ ] **Step 2: Write the test**

`apps/web/tests/App.test.tsx`:
```tsx
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { App } from '../src/App';

describe('App', () => {
  it('renders the Prism heading', () => {
    render(
      <ChakraProvider value={defaultSystem}>
        <App />
      </ChakraProvider>,
    );
    expect(screen.getByRole('heading', { name: /prism/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run test (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/web && npm test
```
Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/web/ && git commit -m "test(web): smoke render of App"
```

---

## Phase 6: API client + auth state in web

### Task 6.1: Axios client and types

**Files:**
- Create: `apps/web/src/api/client.ts`
- Create: `apps/web/src/api/types.ts`

- [ ] **Step 1: Write the client**

`apps/web/src/api/client.ts`:
```ts
import axios from 'axios';

export const api = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
});
```

- [ ] **Step 2: Write API types**

`apps/web/src/api/types.ts`:
```ts
export interface User {
  id: string;
  email: string;
}

export interface Project {
  id: string;
  slug: string;
  name: string;
  description: string;
}

export interface CreateProjectRequest {
  slug: string;
  name: string;
  description?: string;
}
```

- [ ] **Step 3: Commit (no test yet — used in next task)**

```bash
cd /home/tcollins/dev/prism && git add apps/web/src/api/ && git commit -m "feat(web): axios client and shared types"
```

---

### Task 6.2: Auth provider + hooks

**Files:**
- Create: `apps/web/src/auth/AuthProvider.tsx`
- Create: `apps/web/src/auth/useAuth.ts`
- Create: `apps/web/tests/AuthProvider.test.tsx`

- [ ] **Step 1: Write the failing test**

`apps/web/tests/AuthProvider.test.tsx`:
```tsx
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import axios from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthProvider } from '../src/auth/AuthProvider';
import { useAuth } from '../src/auth/useAuth';

vi.mock('axios');

const Probe = () => {
  const { user, status } = useAuth();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="email">{user?.email ?? 'none'}</span>
    </div>
  );
};

describe('AuthProvider', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    const mockedAxios = axios as unknown as { create: ReturnType<typeof vi.fn> };
    mockedAxios.create = vi.fn().mockReturnValue({
      get: vi.fn().mockResolvedValue({ data: { id: '1', email: 'a@b.com' } }),
      post: vi.fn(),
      defaults: { withCredentials: true },
    });
  });

  it('loads the current user on mount', async () => {
    const qc = new QueryClient();
    render(
      <ChakraProvider value={defaultSystem}>
        <QueryClientProvider client={qc}>
          <AuthProvider>
            <Probe />
          </AuthProvider>
        </QueryClientProvider>
      </ChakraProvider>,
    );
    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe('authenticated');
    });
    expect(screen.getByTestId('email').textContent).toBe('a@b.com');
  });
});
```

- [ ] **Step 2: Run test (FAIL — module missing)**

```bash
cd /home/tcollins/dev/prism/apps/web && npm test
```

- [ ] **Step 3: Implement AuthProvider**

`apps/web/src/auth/AuthProvider.tsx`:
```tsx
import { useQuery } from '@tanstack/react-query';
import { createContext, type ReactNode } from 'react';

import { api } from '../api/client';
import type { User } from '../api/types';

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous';

export interface AuthContextValue {
  user: User | null;
  status: AuthStatus;
  refresh: () => Promise<unknown>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const query = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: async () => {
      try {
        const res = await api.get<User>('/auth/me');
        return res.data;
      } catch {
        return null;
      }
    },
    staleTime: 60_000,
  });

  const status: AuthStatus = query.isLoading ? 'loading' : query.data ? 'authenticated' : 'anonymous';

  return (
    <AuthContext.Provider value={{ user: query.data ?? null, status, refresh: query.refetch }}>
      {children}
    </AuthContext.Provider>
  );
}
```

`apps/web/src/auth/useAuth.ts`:
```ts
import { useContext } from 'react';

import { AuthContext, type AuthContextValue } from './AuthProvider';

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
```

- [ ] **Step 4: Wire AuthProvider into main.tsx**

Update `apps/web/src/main.tsx`:
```tsx
import { ChakraProvider } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

import { App } from './App';
import { AuthProvider } from './auth/AuthProvider';
import { system } from './theme';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ChakraProvider value={system}>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </AuthProvider>
      </QueryClientProvider>
    </ChakraProvider>
  </StrictMode>,
);
```

- [ ] **Step 5: Run tests (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/web && npm test
```

- [ ] **Step 6: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/web/ && git commit -m "feat(web): AuthProvider + useAuth"
```

---

## Phase 7: Web routes + login + projects UI

### Task 7.1: Routing skeleton with protected routes

**Files:**
- Create: `apps/web/src/routes/ProtectedRoute.tsx`
- Modify: `apps/web/src/App.tsx`
- Create: `apps/web/src/pages/LoginPage.tsx`
- Create: `apps/web/src/pages/ProjectsPage.tsx`

- [ ] **Step 1: Write LoginPage**

`apps/web/src/pages/LoginPage.tsx`:
```tsx
import { Box, Button, Heading, Input, Stack, Text } from '@chakra-ui/react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { api } from '../api/client';
import { useAuth } from '../auth/useAuth';

export function LoginPage() {
  const { refresh } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.post('/auth/login', { email, password });
      await refresh();
      navigate('/');
    } catch {
      setError('Invalid credentials');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Box maxW="sm" mx="auto" mt={20} p={6} borderWidth={1} borderRadius="lg">
      <Heading size="lg" mb={4}>
        Sign in to Prism
      </Heading>
      <form onSubmit={handleSubmit}>
        <Stack gap={3}>
          <Input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <Input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {error && (
            <Text color="red.400" fontSize="sm">
              {error}
            </Text>
          )}
          <Button type="submit" colorPalette="blue" loading={submitting}>
            Sign in
          </Button>
        </Stack>
      </form>
    </Box>
  );
}
```

- [ ] **Step 2: Write ProjectsPage**

`apps/web/src/pages/ProjectsPage.tsx`:
```tsx
import { Box, Button, Heading, Input, Stack, Table, Text } from '@chakra-ui/react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { api } from '../api/client';
import type { CreateProjectRequest, Project } from '../api/types';

export function ProjectsPage() {
  const qc = useQueryClient();
  const projectsQuery = useQuery({
    queryKey: ['projects'],
    queryFn: async () => (await api.get<Project[]>('/projects')).data,
  });

  const [slug, setSlug] = useState('');
  const [name, setName] = useState('');

  const createMutation = useMutation({
    mutationFn: async (body: CreateProjectRequest) => {
      const res = await api.post<Project>('/projects', body);
      return res.data;
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['projects'] });
      setSlug('');
      setName('');
    },
  });

  return (
    <Box p={8}>
      <Heading size="xl" mb={6}>
        Projects
      </Heading>

      <Stack
        as="form"
        gap={2}
        direction={{ base: 'column', md: 'row' }}
        mb={6}
        onSubmit={(e) => {
          e.preventDefault();
          createMutation.mutate({ slug, name });
        }}
      >
        <Input placeholder="slug (e.g. audio-codec)" value={slug} onChange={(e) => setSlug(e.target.value)} />
        <Input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
        <Button type="submit" colorPalette="blue" loading={createMutation.isPending}>
          Create
        </Button>
      </Stack>
      {createMutation.isError && (
        <Text color="red.400" mb={4}>
          Could not create project — slug may already exist or be invalid.
        </Text>
      )}

      {projectsQuery.isLoading && <Text>Loading…</Text>}
      {projectsQuery.data && projectsQuery.data.length === 0 && (
        <Text color="gray.500">No projects yet.</Text>
      )}
      {projectsQuery.data && projectsQuery.data.length > 0 && (
        <Table.Root variant="outline">
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeader>Slug</Table.ColumnHeader>
              <Table.ColumnHeader>Name</Table.ColumnHeader>
              <Table.ColumnHeader>Description</Table.ColumnHeader>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {projectsQuery.data.map((p) => (
              <Table.Row key={p.id}>
                <Table.Cell>{p.slug}</Table.Cell>
                <Table.Cell>{p.name}</Table.Cell>
                <Table.Cell>{p.description}</Table.Cell>
              </Table.Row>
            ))}
          </Table.Body>
        </Table.Root>
      )}
    </Box>
  );
}
```

- [ ] **Step 3: Write ProtectedRoute**

`apps/web/src/routes/ProtectedRoute.tsx`:
```tsx
import { Navigate } from 'react-router-dom';

import { useAuth } from '../auth/useAuth';

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  if (status === 'loading') return null;
  if (status === 'anonymous') return <Navigate to="/login" replace />;
  return <>{children}</>;
}
```

- [ ] **Step 4: Update App.tsx with routes**

`apps/web/src/App.tsx`:
```tsx
import { Route, Routes } from 'react-router-dom';

import { LoginPage } from './pages/LoginPage';
import { ProjectsPage } from './pages/ProjectsPage';
import { ProtectedRoute } from './routes/ProtectedRoute';

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <ProjectsPage />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
```

- [ ] **Step 5: Update App.test.tsx (since heading changed)**

`apps/web/tests/App.test.tsx`:
```tsx
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import axios from 'axios';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { App } from '../src/App';
import { AuthProvider } from '../src/auth/AuthProvider';

vi.mock('axios');

describe('App', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    const mockedAxios = axios as unknown as { create: ReturnType<typeof vi.fn> };
    mockedAxios.create = vi.fn().mockReturnValue({
      get: vi.fn().mockRejectedValue(new Error('401')),
      post: vi.fn(),
      defaults: { withCredentials: true },
    });
  });

  it('redirects unauthenticated users to /login', async () => {
    const qc = new QueryClient();
    render(
      <ChakraProvider value={defaultSystem}>
        <QueryClientProvider client={qc}>
          <AuthProvider>
            <MemoryRouter initialEntries={['/']}>
              <App />
            </MemoryRouter>
          </AuthProvider>
        </QueryClientProvider>
      </ChakraProvider>,
    );
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /sign in to prism/i })).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 6: Run all web tests (PASS)**

```bash
cd /home/tcollins/dev/prism/apps/web && npm test
```
Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/web/ && git commit -m "feat(web): login + projects pages with protected routing"
```

---

## Phase 8: Continuous integration

### Task 8.1: Lint workflow

**Files:**
- Create: `.github/workflows/lint.yml`

- [ ] **Step 1: Write the workflow**

`.github/workflows/lint.yml`:
```yaml
name: lint

on:
  push:
    branches: [main]
  pull_request:

jobs:
  api:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with: { version: latest }
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - working-directory: apps/api
        run: |
          uv pip install --system .[dev] || uv sync
          uv run ruff check .
          uv run mypy src

  web:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: apps/web/package-lock.json
      - working-directory: apps/web
        run: |
          npm ci || npm install
          npm run lint
```

- [ ] **Step 2: Smoke check locally**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run ruff check . && uv run mypy src
cd /home/tcollins/dev/prism/apps/web && npm run lint
```
Expected: zero errors. Fix any reported issues before committing.

- [ ] **Step 3: Commit**

```bash
cd /home/tcollins/dev/prism && git add .github/ && git commit -m "ci: lint workflow for api and web"
```

---

### Task 8.2: Backend test workflow

**Files:**
- Create: `.github/workflows/test-backend.yml`

- [ ] **Step 1: Write the workflow**

`.github/workflows/test-backend.yml`:
```yaml
name: test-backend

on:
  push:
    branches: [main]
  pull_request:

jobs:
  pytest:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: prism
          POSTGRES_USER: prism
          POSTGRES_PASSWORD: prism
        ports: ['5432:5432']
        options: >-
          --health-cmd "pg_isready -U prism"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - working-directory: apps/api
        env:
          PRISM_DATABASE_URL: postgresql+psycopg://prism:prism@localhost:5432/prism
          PRISM_S3_ENDPOINT: http://x
          PRISM_S3_ACCESS_KEY: x
          PRISM_S3_SECRET_KEY: x
          PRISM_S3_BUCKET: x
          PRISM_REDIS_URL: redis://localhost:6379/0
          PRISM_JWT_SECRET: ci-secret
        run: |
          uv pip install --system .[dev] || uv sync
          uv run pytest -v
```

- [ ] **Step 2: Commit**

```bash
cd /home/tcollins/dev/prism && git add .github/workflows/test-backend.yml && git commit -m "ci: backend test workflow"
```

---

### Task 8.3: Frontend test workflow

**Files:**
- Create: `.github/workflows/test-frontend.yml`

- [ ] **Step 1: Write the workflow**

`.github/workflows/test-frontend.yml`:
```yaml
name: test-frontend

on:
  push:
    branches: [main]
  pull_request:

jobs:
  vitest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: apps/web/package-lock.json
      - working-directory: apps/web
        run: |
          npm ci || npm install
          npm run build
          npm test
```

- [ ] **Step 2: Commit**

```bash
cd /home/tcollins/dev/prism && git add .github/workflows/test-frontend.yml && git commit -m "ci: frontend test workflow"
```

---

## Phase 9: Stack smoke test

### Task 9.1: docker compose up end-to-end

This task is a manual smoke check — no commit required, just verify everything works together.

- [ ] **Step 1: Bring up the stack**

```bash
cd /home/tcollins/dev/prism && cp -n deploy/.env.example deploy/.env || true && \
  docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml --env-file deploy/.env up --build -d
```

- [ ] **Step 2: Wait for health and run alembic**

```bash
docker compose -f /home/tcollins/dev/prism/deploy/docker-compose.yml -f /home/tcollins/dev/prism/deploy/docker-compose.dev.yml --env-file /home/tcollins/dev/prism/deploy/.env exec api alembic upgrade head
```

- [ ] **Step 3: Hit the API**

```bash
curl -s http://localhost:8000/api/v1/health
```
Expected: `{"status":"ok","version":"0.1.0"}`

- [ ] **Step 4: Log in and create a project**

```bash
curl -s -c /tmp/prism_cookies.txt -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"change-me-in-prod"}' \
  http://localhost:8000/api/v1/auth/login

curl -s -b /tmp/prism_cookies.txt -H 'Content-Type: application/json' \
  -d '{"slug":"audio-codec","name":"Audio Codec"}' \
  http://localhost:8000/api/v1/projects

curl -s -b /tmp/prism_cookies.txt http://localhost:8000/api/v1/projects
```
Expected: project appears in the list.

- [ ] **Step 5: Open the web UI**

Browser: http://localhost:8080 → log in with `admin@example.com` / `change-me-in-prod` → see "audio-codec" in the projects list. Create another project from the form.

- [ ] **Step 6: Tear down**

```bash
cd /home/tcollins/dev/prism && docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml --env-file deploy/.env down
```

- [ ] **Step 7: Tag the milestone (optional)**

```bash
cd /home/tcollins/dev/prism && git tag v0.1.0-walking-skeleton
```

---

## What's next

This walking skeleton is intentionally narrow — it proves the plumbing works end to end. The follow-up plans build out the real product:

- **Plan 2 — Ingest Pipeline:** add the `Artifact`, `DerivedArtifact`, `TestRun`, `TestSuite`, `TestCase`, `RunTag` models; MinIO storage layer; JUnit + waveform parsers; Celery worker; `POST /runs` upload endpoint with archive extraction.
- **Plan 3 — Browsing & DSP:** read endpoints for runs/suites/cases/artifacts; server-side waveform downsampling; FFT computation with caching; dashboard, run-detail, and plot UI.
- **Plan 4 — Comparison & Polish:** `POST /compare` and `GET /compare/waveforms`; comparison UI with overlay plots and diff table; prod nginx + image build CI; MkDocs site; Playwright E2E.
