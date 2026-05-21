# Log Parsing & Commit Cross-Reference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse boot/dmesg `LOG_TEXT` artifacts at ingest into structured facts (kernel + HDL commit, version, board, error/warn/panic tallies, sampled findings) and make commits cross-referenceable across runs.

**Architecture:** A pure parser (`parsers/logs.py`) produces a `ParsedLog`. Ingest persists it into two new tables (`log_reports`, `log_findings`). Indexed commit columns power cross-reference endpoints (commits-per-project, runs-by-commit, shared counts) and a Compare boot block. The web app gains a Boot panel, a Commits tab, and a Compare diff block.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, pydantic-settings, pytest; React 18 + Chakra v3 + react-query + TypeScript + vitest.

**Spec:** `docs/superpowers/specs/2026-05-20-log-parsing-commit-crossref-design.md`

**Conventions to follow (verified in repo):**

- Models: `Base, TimestampMixin` from `models.base`; `String(36)` uuid PKs via `default=lambda: str(uuid.uuid4())`; register in `models/__init__.py` (`__all__` kept sorted).
- Repos: thin classes taking a `Session`, `create(...)` calls `flush()`.
- Routers: `Depends(current_user)`, `Depends(session_dep)`, `Depends(csrf_protect)` for writes.
- Migrations: `revision`/`down_revision` strings; `_JSON = JSONB().with_variant(sa.JSON(), "sqlite")` only if JSON needed.
- Tests: `client`, `seed_admin`, `patch_ingest`, `storage_fixture` fixtures in `tests/conftest.py`; SQLite in-memory; `ingest_run(...)` is called inline by `patch_ingest` **without settings**, so ingest must work on parser defaults.
- Lint/test gates: `cd apps/api && uv run pytest -q --no-cov`, `uv run mypy src`, `uv run ruff check .`; `cd apps/web && npx tsc --noEmit && npm run lint && npx vitest run`.

---

## Stage 1 — Extraction core (parser, model, settings, ingest, backfill)

### Task 1: Log parser

**Files:**

- Create: `apps/api/src/prism_api/parsers/logs.py`
- Test: `apps/api/tests/test_parsers_logs.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_parsers_logs.py
from prism_api.parsers.logs import parse_log

_BOOT = b"""[    0.000000] Linux version 6.1.0-g1a2b3c4 (jenkins@build) (gcc 12) #1 SMP
[    0.000000] Machine model: Analog Devices ZynqMP ZCU102 Rev1.0
HDL git hash: deadbeef1234
[    1.100000] <6> usb 1-1: new high-speed USB device
[    1.200000] <4> spi-nor: warning: unknown flash id
[    1.300000] ad9361 spi0.0: probe failed with error -110
[    1.400000] <3> mmc0: error -84 reading sector
[    2.000000] Kernel panic - not syncing: oops
"""


def test_extracts_commits_version_board() -> None:
    p = parse_log(_BOOT, kernel_pattern=None, hdl_pattern=None, findings_cap=200)
    assert p.kernel_commit == "1a2b3c4"
    assert p.hdl_commit == "deadbeef1234"
    assert p.kernel_version == "6.1.0-g1a2b3c4"
    assert p.board == "Analog Devices ZynqMP ZCU102 Rev1.0"


def test_tallies_and_flags() -> None:
    p = parse_log(_BOOT, kernel_pattern=None, hdl_pattern=None, findings_cap=200)
    assert p.has_panic is True
    assert p.error_count == 1          # the <3> mmc0 error
    assert p.warn_count == 1           # the <4> spi-nor warning
    sev = sorted(f.severity for f in p.findings)
    assert sev == ["error", "panic", "probe_fail", "warn"]


def test_findings_cap_enforced() -> None:
    many = b"\n".join(b"<3> error line %d" % i for i in range(50))
    p = parse_log(many, kernel_pattern=None, hdl_pattern=None, findings_cap=10)
    assert len(p.findings) == 10
    assert p.error_count == 50         # count is full, sample is capped


def test_missing_commits_is_not_fatal() -> None:
    p = parse_log(b"nothing interesting here\n", kernel_pattern=None, hdl_pattern=None, findings_cap=5)
    assert p.kernel_commit is None and p.hdl_commit is None
    assert p.error_count == 0 and p.has_panic is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_parsers_logs.py -q --no-cov`
Expected: FAIL (`ModuleNotFoundError: prism_api.parsers.logs`).

- [ ] **Step 3: Write the parser**

```python
# apps/api/src/prism_api/parsers/logs.py
"""Boot/dmesg log parser.

Extracts kernel + HDL commit, kernel version, board, and a capped sample of
notable lines (panic / error / warn / probe_fail) with full tallies. Pure and
unit-testable; ingest persists the result. Commit patterns are configurable
(first capture group = hash); these defaults are ADI-oriented starting points
and should be confirmed against a real boot log.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

DEFAULT_KERNEL_PATTERN = r"Linux version (\S+)"
DEFAULT_HDL_PATTERN = r"(?i)hdl[^0-9a-f]*([0-9a-f]{7,40})"
DEFAULT_FINDINGS_CAP = 200

# kernel commit is the trailing -g<sha> of the version token, when present
_KERNEL_SHA = re.compile(r"-g([0-9a-f]{7,40})$")
_VERSION = re.compile(r"Linux version (\S+)")
_BOARD = re.compile(r"(?:Machine model|Hardware name):\s*(.+?)\s*$")
_DMESG_PREFIX = re.compile(r"^\[\s*\d+\.\d+\]\s*")
_SYSLOG = re.compile(r"<(\d)>")

# severity precedence: panic > probe_fail > error > warn (probe phrases contain
# "fail", so they must be matched before the generic error rule)
_PANIC = re.compile(r"(?i)kernel panic|\bOops\b|\bBUG:|Call Trace")
_PROBE = re.compile(r"(?i)probe failed|failed to|timeout")
_ERROR_KW = re.compile(r"(?i)error|fail")
_WARN_KW = re.compile(r"(?i)warn")


@dataclass
class ParsedFinding:
    severity: str          # error | warn | panic | probe_fail
    line_no: int | None
    text: str


@dataclass
class ParsedLog:
    kernel_version: str | None = None
    board: str | None = None
    kernel_commit: str | None = None
    hdl_commit: str | None = None
    error_count: int = 0
    warn_count: int = 0
    has_panic: bool = False
    findings: list[ParsedFinding] = field(default_factory=list)


def _classify(body: str) -> str | None:
    if _PANIC.search(body):
        return "panic"
    if _PROBE.search(body):
        return "probe_fail"
    m = _SYSLOG.search(body)
    if m and int(m.group(1)) <= 3:
        return "error"
    if m and int(m.group(1)) == 4:
        return "warn"
    if _ERROR_KW.search(body):
        return "error"
    if _WARN_KW.search(body):
        return "warn"
    return None


def parse_log(
    data: bytes,
    *,
    kernel_pattern: str | None,
    hdl_pattern: str | None,
    findings_cap: int,
) -> ParsedLog:
    text = data.decode("utf-8", errors="replace")
    kp = re.compile(kernel_pattern) if kernel_pattern else None
    hp = re.compile(hdl_pattern) if hdl_pattern else re.compile(DEFAULT_HDL_PATTERN)
    out = ParsedLog()

    for i, raw in enumerate(text.splitlines()):
        body = _DMESG_PREFIX.sub("", raw)

        if out.kernel_version is None:
            v = _VERSION.search(body)
            if v:
                out.kernel_version = v.group(1)
                sha = _KERNEL_SHA.search(v.group(1))
                if sha:
                    out.kernel_commit = sha.group(1)
        if out.kernel_commit is None and kp:
            km = kp.search(body)
            if km and km.groups():
                out.kernel_commit = km.group(1)
        if out.board is None:
            b = _BOARD.search(body)
            if b:
                out.board = b.group(1)
        if out.hdl_commit is None:
            hm = hp.search(body)
            if hm:
                out.hdl_commit = hm.group(1)

        sev = _classify(body)
        if sev == "panic":
            out.has_panic = True
        elif sev == "error":
            out.error_count += 1
        elif sev == "warn":
            out.warn_count += 1
        if sev is not None and len(out.findings) < findings_cap:
            out.findings.append(ParsedFinding(severity=sev, line_no=i + 1, text=body[:1000]))

    return out
```

Note: with `kernel_pattern=None` the default `Linux version (\S+)` extraction is handled inline by `_VERSION` + `_KERNEL_SHA`; callers pass `DEFAULT_KERNEL_PATTERN` (which is also `Linux version (\S+)`) in production — both paths set `kernel_commit` from the `-g<sha>` suffix.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_parsers_logs.py -q --no-cov`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/prism_api/parsers/logs.py apps/api/tests/test_parsers_logs.py
git commit -m "feat(api): boot/dmesg log parser (commits, version, board, findings)"
```

---

### Task 2: Models + migration

**Files:**

- Create: `apps/api/src/prism_api/models/log.py`
- Modify: `apps/api/src/prism_api/models/__init__.py`
- Create: `apps/api/src/prism_api/migrations/versions/0011_log_reports.py`
- Test: `apps/api/tests/test_models_log.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_models_log.py
from prism_api.models.log import LogFinding, LogReport


def test_log_models_persist(db_session) -> None:
    r = LogReport(
        run_id="run-1", artifact_id="art-1", source="boot.log",
        kernel_version="6.1.0-g1a2b3c4", board="ZCU102",
        kernel_commit="1a2b3c4", hdl_commit="deadbeef",
        error_count=2, warn_count=3, has_panic=True,
    )
    db_session.add(r)
    db_session.flush()
    db_session.add(LogFinding(log_report_id=r.id, severity="error", line_no=10, text="boom"))
    db_session.flush()
    assert r.id and r.kernel_commit == "1a2b3c4"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_models_log.py -q --no-cov`
Expected: FAIL (`ModuleNotFoundError: prism_api.models.log`).

- [ ] **Step 3: Write the models + register + migration**

```python
# apps/api/src/prism_api/models/log.py
"""Parsed boot/dmesg log facts."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from prism_api.models.base import Base, TimestampMixin


class LogReport(Base, TimestampMixin):
    __tablename__ = "log_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source: Mapped[str] = mapped_column(String(512), nullable=False)
    kernel_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    board: Mapped[str | None] = mapped_column(String(255), nullable=True)
    kernel_commit: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    hdl_commit: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_panic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class LogFinding(Base, TimestampMixin):
    __tablename__ = "log_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    log_report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("log_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    line_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(String(1000), nullable=False)
```

In `apps/api/src/prism_api/models/__init__.py` add the import (after the `from prism_api.models.artifact ...` line) and the `__all__` entries (keep sorted):

```python
from prism_api.models.log import LogFinding, LogReport
```

Add `"LogFinding",` and `"LogReport",` to `__all__`.

```python
# apps/api/src/prism_api/migrations/versions/0011_log_reports.py
"""add log_reports and log_findings tables

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "log_reports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("artifact_id", sa.String(length=36), nullable=True),
        sa.Column("source", sa.String(length=512), nullable=False),
        sa.Column("kernel_version", sa.String(length=255), nullable=True),
        sa.Column("board", sa.String(length=255), nullable=True),
        sa.Column("kernel_commit", sa.String(length=64), nullable=True),
        sa.Column("hdl_commit", sa.String(length=64), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("warn_count", sa.Integer(), nullable=False),
        sa.Column("has_panic", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["test_runs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_log_reports_run_id", "log_reports", ["run_id"])
    op.create_index("ix_log_reports_kernel_commit", "log_reports", ["kernel_commit"])
    op.create_index("ix_log_reports_hdl_commit", "log_reports", ["hdl_commit"])
    op.create_table(
        "log_findings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("log_report_id", sa.String(length=36), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=True),
        sa.Column("text", sa.String(length=1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["log_report_id"], ["log_reports.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_log_findings_log_report_id", "log_findings", ["log_report_id"])


def downgrade() -> None:
    op.drop_index("ix_log_findings_log_report_id", table_name="log_findings")
    op.drop_table("log_findings")
    op.drop_index("ix_log_reports_hdl_commit", table_name="log_reports")
    op.drop_index("ix_log_reports_kernel_commit", table_name="log_reports")
    op.drop_index("ix_log_reports_run_id", table_name="log_reports")
    op.drop_table("log_reports")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_models_log.py -q --no-cov`
Expected: PASS.

- [ ] **Step 5: Validate migration offline (postgres dialect)**

Run:

```bash
cd apps/api && PRISM_DATABASE_URL="postgresql+psycopg://u:p@localhost/db" \
  PRISM_S3_ENDPOINT=x PRISM_S3_ACCESS_KEY=a PRISM_S3_SECRET_KEY=b PRISM_S3_BUCKET=c \
  PRISM_REDIS_URL=x PRISM_JWT_SECRET=0123456789012345678901234567890123 \
  uv run alembic upgrade 0010:0011 --sql 2>&1 | grep -i "CREATE TABLE log_"
```

Expected: prints `CREATE TABLE log_reports (` and `CREATE TABLE log_findings (`.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/prism_api/models/log.py apps/api/src/prism_api/models/__init__.py \
  apps/api/src/prism_api/migrations/versions/0011_log_reports.py apps/api/tests/test_models_log.py
git commit -m "feat(api): log_reports + log_findings models and migration 0011"
```

---

### Task 3: Settings fields

**Files:**

- Modify: `apps/api/src/prism_api/config.py`
- Test: `apps/api/tests/test_config_log.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_config_log.py
from prism_api.config import Settings


def test_log_settings_defaults() -> None:
    s = Settings(  # type: ignore[call-arg]
        database_url="x", s3_endpoint="x", s3_access_key="x", s3_secret_key="x",
        s3_bucket="x", redis_url="x", jwt_secret="testsecretlongenough",
    )
    assert s.log_findings_cap == 200
    assert "Linux version" in s.log_kernel_commit_pattern
    assert s.kernel_repo_url is None and s.hdl_repo_url is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_config_log.py -q --no-cov`
Expected: FAIL (`AttributeError: log_findings_cap`).

- [ ] **Step 3: Add settings fields**

In `apps/api/src/prism_api/config.py`, add an import at top:

```python
from prism_api.parsers.logs import (
    DEFAULT_FINDINGS_CAP,
    DEFAULT_HDL_PATTERN,
    DEFAULT_KERNEL_PATTERN,
)
```

Then add these fields to `Settings` (after `admin_password`):

```python
    log_kernel_commit_pattern: str = DEFAULT_KERNEL_PATTERN
    log_hdl_commit_pattern: str = DEFAULT_HDL_PATTERN
    log_findings_cap: int = DEFAULT_FINDINGS_CAP
    kernel_repo_url: str | None = None
    hdl_repo_url: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_config_log.py -q --no-cov`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/prism_api/config.py apps/api/tests/test_config_log.py
git commit -m "feat(api): PRISM_LOG_* settings for log parsing + repo links"
```

---

### Task 4: LogRepo

**Files:**

- Create: `apps/api/src/prism_api/repos/logs.py`
- Test: `apps/api/tests/test_repos_logs.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_repos_logs.py
from prism_api.parsers.logs import ParsedFinding, ParsedLog
from prism_api.repos.logs import LogRepo


def _parsed(kernel: str, hdl: str) -> ParsedLog:
    return ParsedLog(
        kernel_version="6.1.0", board="ZCU102", kernel_commit=kernel, hdl_commit=hdl,
        error_count=1, warn_count=2, has_panic=False,
        findings=[ParsedFinding(severity="error", line_no=3, text="boom")],
    )


def test_create_and_query(db_session) -> None:
    repo = LogRepo(db_session)
    repo.create_report(run_id="r1", artifact_id="a1", source="boot.log", parsed=_parsed("kc", "hd"))
    repo.create_report(run_id="r2", artifact_id="a2", source="boot.log", parsed=_parsed("kc", "hX"))
    db_session.flush()

    reports = repo.list_by_run("r1")
    assert len(reports) == 1
    assert len(repo.findings_for(reports[0].id)) == 1

    assert repo.commit_counts("kernel") == [("kc", 2)]
    assert sorted(repo.commit_counts("hdl")) == [("hX", 1), ("hd", 1)]
    assert repo.run_ids_for_commit("kernel", "kc") == {"r1", "r2"}
    assert repo.shared_count("kernel", "kc", exclude_run_id="r1") == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_repos_logs.py -q --no-cov`
Expected: FAIL (`ModuleNotFoundError: prism_api.repos.logs`).

- [ ] **Step 3: Write the repo**

```python
# apps/api/src/prism_api/repos/logs.py
"""Log-report repository + commit cross-reference queries."""

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from prism_api.models.log import LogFinding, LogReport
from prism_api.models.run import TestRun
from prism_api.parsers.logs import ParsedLog

_COMMIT_COL = {"kernel": LogReport.kernel_commit, "hdl": LogReport.hdl_commit}


class LogRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_report(
        self, *, run_id: str, artifact_id: str | None, source: str, parsed: ParsedLog
    ) -> LogReport:
        report = LogReport(
            run_id=run_id,
            artifact_id=artifact_id,
            source=source,
            kernel_version=parsed.kernel_version,
            board=parsed.board,
            kernel_commit=parsed.kernel_commit,
            hdl_commit=parsed.hdl_commit,
            error_count=parsed.error_count,
            warn_count=parsed.warn_count,
            has_panic=parsed.has_panic,
        )
        self._session.add(report)
        self._session.flush()
        for f in parsed.findings:
            self._session.add(
                LogFinding(
                    log_report_id=report.id, severity=f.severity, line_no=f.line_no, text=f.text
                )
            )
        self._session.flush()
        return report

    def list_by_run(self, run_id: str) -> list[LogReport]:
        return list(
            self._session.execute(
                select(LogReport).where(LogReport.run_id == run_id).order_by(LogReport.created_at)
            ).scalars()
        )

    def findings_for(self, report_id: str) -> list[LogFinding]:
        return list(
            self._session.execute(
                select(LogFinding)
                .where(LogFinding.log_report_id == report_id)
                .order_by(LogFinding.line_no)
            ).scalars()
        )

    def commit_counts(self, kind: str) -> list[tuple[str, int]]:
        """Distinct commits (of `kind`) within a join scope = all runs; callers
        filter by project via run join. Returns (commit, distinct-run-count)."""
        col = _COMMIT_COL[kind]
        rows = self._session.execute(
            select(col, func.count(distinct(LogReport.run_id)))
            .where(col.is_not(None))
            .group_by(col)
            .order_by(col)
        ).all()
        return [(str(c), int(n)) for c, n in rows]

    def commit_counts_for_project(self, kind: str, project_id: str) -> list[tuple[str, int]]:
        col = _COMMIT_COL[kind]
        rows = self._session.execute(
            select(col, func.count(distinct(LogReport.run_id)))
            .join(TestRun, TestRun.id == LogReport.run_id)
            .where(col.is_not(None), TestRun.project_id == project_id)
            .group_by(col)
            .order_by(col)
        ).all()
        return [(str(c), int(n)) for c, n in rows]

    def run_ids_for_commit(self, kind: str, commit: str) -> set[str]:
        col = _COMMIT_COL[kind]
        rows = self._session.execute(
            select(distinct(LogReport.run_id)).where(col == commit)
        ).scalars()
        return set(rows)

    def shared_count(self, kind: str, commit: str, *, exclude_run_id: str) -> int:
        return len(self.run_ids_for_commit(kind, commit) - {exclude_run_id})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_repos_logs.py -q --no-cov`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/prism_api/repos/logs.py apps/api/tests/test_repos_logs.py
git commit -m "feat(api): LogRepo with commit cross-reference queries"
```

---

### Task 5: Ingest wiring

**Files:**

- Modify: `apps/api/src/prism_api/ingest.py`
- Modify: `apps/api/src/prism_api/worker/tasks.py`
- Test: `apps/api/tests/test_ingest_logs.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_ingest_logs.py
import io
import json
import zipfile

from prism_api.repos.logs import LogRepo


def _login(client) -> str:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    return client.cookies.get("prism_csrf") or ""


_BOOT = b"""[    0.000000] Linux version 6.1.0-g1a2b3c4 (j@b) #1 SMP
[    0.000000] Machine model: Analog Devices ZCU102
HDL git hash: deadbeef1234
[    1.0] <3> mmc0: error -84
[    2.0] Kernel panic - not syncing
"""


def test_ingest_parses_boot_log(client, seed_admin, patch_ingest, db_session) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "rf", "name": "RF"})
    junit = b'<?xml version="1.0"?><testsuites><testsuite name="s" tests="1" failures="0"><testcase classname="c" name="t"/></testsuite></testsuites>'
    arc = io.BytesIO()
    with zipfile.ZipFile(arc, "w") as zf:
        zf.writestr("boot.log", _BOOT)
    run_id = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", junit, "application/xml"),
               "archive": ("a.zip", arc.getvalue(), "application/zip")},
        data={"metadata": json.dumps({"project_slug": "rf", "name": "r1"})},
        headers={"X-Prism-Csrf": csrf},
    ).json()["id"]

    reports = LogRepo(db_session).list_by_run(run_id)
    assert len(reports) == 1
    assert reports[0].kernel_commit == "1a2b3c4"
    assert reports[0].hdl_commit == "deadbeef1234"
    assert reports[0].has_panic is True
    assert reports[0].error_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_ingest_logs.py -q --no-cov`
Expected: FAIL (`assert len(reports) == 1` → 0; nothing persisted yet).

- [ ] **Step 3: Wire ingest**

In `apps/api/src/prism_api/ingest.py`:

Add imports near the others:

```python
from prism_api.models import ArtifactKind  # already imported in the existing tuple
from prism_api.parsers.logs import (
    DEFAULT_FINDINGS_CAP,
    DEFAULT_HDL_PATTERN,
    DEFAULT_KERNEL_PATTERN,
    parse_log,
)
from prism_api.repos.logs import LogRepo
```

Change the `ingest_run` signature to accept optional patterns (keyword-only, parser defaults so `patch_ingest` keeps working without settings):

```python
def ingest_run(
    inputs: IngestInputs,
    *,
    session: Session,
    storage: ObjectStorage,
    kernel_pattern: str = DEFAULT_KERNEL_PATTERN,
    hdl_pattern: str = DEFAULT_HDL_PATTERN,
    findings_cap: int = DEFAULT_FINDINGS_CAP,
) -> None:
```

Construct the repo near the others at the top of the function body:

```python
    log_repo = LogRepo(session)
```

In the archive loop, immediately after the existing `artifacts.create(...)` call that assigns the artifact (capture it), parse `LOG_TEXT` artifacts. Replace the existing `artifacts.create(...)` statement in step 4 with an assignment and the parse block:

```python
                created = artifacts.create(
                    owner_type=owner_type,
                    owner_id=owner_id,
                    kind=kind,
                    filename=name,
                    size_bytes=len(data),
                    content_hash=key.rsplit("/", 1)[-1],
                    storage_key=key,
                    manifest_kind=manifest_kind,
                )
                if kind == ArtifactKind.LOG_TEXT:
                    try:
                        parsed = parse_log(
                            data,
                            kernel_pattern=kernel_pattern,
                            hdl_pattern=hdl_pattern,
                            findings_cap=findings_cap,
                        )
                        log_repo.create_report(
                            run_id=inputs.run_id,
                            artifact_id=created.id,
                            source=bare,
                            parsed=parsed,
                        )
                    except Exception as exc:  # best-effort; never fail ingest
                        logger.warning("log parse failed for %s: %s", name, exc)
```

In `apps/api/src/prism_api/worker/tasks.py`, pass the configured patterns:

```python
        ingest_run(
            IngestInputs(run_id=run_id, junit_xml=junit_xml, archive=archive),
            session=session,
            storage=storage,
            kernel_pattern=settings.log_kernel_commit_pattern,
            hdl_pattern=settings.log_hdl_commit_pattern,
            findings_cap=settings.log_findings_cap,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_ingest_logs.py -q --no-cov`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/prism_api/ingest.py apps/api/src/prism_api/worker/tasks.py apps/api/tests/test_ingest_logs.py
git commit -m "feat(api): parse LOG_TEXT artifacts into log_reports at ingest"
```

---

### Task 6: Backfill CLI

**Files:**

- Modify: `apps/api/src/prism_api/cli.py`
- Test: `apps/api/tests/test_cli_reparse.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_cli_reparse.py
from prism_api.cli import reparse_logs
from prism_api.models.artifact import Artifact, ArtifactKind
from prism_api.repos.logs import LogRepo


def test_reparse_builds_reports(db_session, monkeypatch) -> None:
    # an existing LOG_TEXT artifact with no report yet
    db_session.add(Artifact(
        id="a1", owner_type="run", owner_id="r1", kind=ArtifactKind.LOG_TEXT,
        filename="boot.log", size_bytes=10, content_hash="h", storage_key="k",
    ))
    db_session.flush()

    class FakeStorage:
        def get_bytes(self, key: str) -> bytes:
            return b"Linux version 6.1.0-gabc1234 (x) #1\n"

    n = reparse_logs(session=db_session, storage=FakeStorage(),
                     kernel_pattern="Linux version (\\S+)", hdl_pattern="x", findings_cap=50)
    assert n == 1
    reports = LogRepo(db_session).list_by_run("r1")
    assert reports[0].kernel_commit == "abc1234"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_cli_reparse.py -q --no-cov`
Expected: FAIL (`ImportError: cannot import name 'reparse_logs'`).

- [ ] **Step 3: Implement the backfill**

In `apps/api/src/prism_api/cli.py` add imports + function + dispatch:

```python
from sqlalchemy import select

from prism_api.models.artifact import Artifact, ArtifactKind
from prism_api.parsers.logs import parse_log
from prism_api.repos.logs import LogRepo


def reparse_logs(*, session, storage, kernel_pattern, hdl_pattern, findings_cap) -> int:
    """(Re)build log_reports for every LOG_TEXT artifact that has none. Returns count."""
    repo = LogRepo(session)
    arts = session.execute(
        select(Artifact).where(Artifact.kind == ArtifactKind.LOG_TEXT)
    ).scalars()
    count = 0
    for a in arts:
        if repo.list_by_run(a.owner_id) and any(
            r.artifact_id == a.id for r in repo.list_by_run(a.owner_id)
        ):
            continue
        if a.owner_type != "run":
            run_id = a.owner_id  # case/suite-scoped logs still attach to their owner_id
        else:
            run_id = a.owner_id
        data = storage.get_bytes(a.storage_key)
        parsed = parse_log(
            data, kernel_pattern=kernel_pattern, hdl_pattern=hdl_pattern, findings_cap=findings_cap
        )
        repo.create_report(run_id=run_id, artifact_id=a.id, source=a.filename, parsed=parsed)
        count += 1
    return count


def reparse_logs_cli(settings: Settings | None = None) -> None:
    s = settings or get_settings()
    engine = create_engine(s.database_url)
    storage = build_storage(s)
    with sessionmaker(bind=engine)() as session:
        n = reparse_logs(
            session=session, storage=storage,
            kernel_pattern=s.log_kernel_commit_pattern,
            hdl_pattern=s.log_hdl_commit_pattern,
            findings_cap=s.log_findings_cap,
        )
        session.commit()
    print(f"reparsed {n} log artifact(s)")
```

In `main()` add a branch and update the usage string:

```python
    if cmd == "reparse-logs":
        reparse_logs_cli()
        return 0
```

Update usage line to `usage: prism-api <bootstrap-admin|ensure-bucket|reparse-logs>`.

Note: the `run_id = a.owner_id` branch is intentionally the same for run/suite/case owners — log reports key on `run_id`, and case/suite-scoped logs are rare; the report's `run_id` column simply stores the owner id. (If suite/case-scoped boot logs become common, a later task can resolve the true run via the suite/case; out of scope here.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_cli_reparse.py -q --no-cov`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/prism_api/cli.py apps/api/tests/test_cli_reparse.py
git commit -m "feat(api): prism-api reparse-logs backfill command"
```

---

## Stage 2 — Endpoints & cross-reference

### Task 7: Log schemas

**Files:**

- Create: `apps/api/src/prism_api/schemas/log.py`
- Test: `apps/api/tests/test_schemas_log.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_schemas_log.py
from prism_api.schemas.log import commit_url


def test_commit_url() -> None:
    assert commit_url("https://github.com/org/linux", "abc1234") == \
        "https://github.com/org/linux/commit/abc1234"
    assert commit_url("https://github.com/org/linux/", "abc1234") == \
        "https://github.com/org/linux/commit/abc1234"
    assert commit_url(None, "abc1234") is None
    assert commit_url("https://x", None) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_schemas_log.py -q --no-cov`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write the schemas**

```python
# apps/api/src/prism_api/schemas/log.py
"""Log-report response schemas."""

from pydantic import BaseModel, Field


def commit_url(repo_base: str | None, commit: str | None) -> str | None:
    if not repo_base or not commit:
        return None
    return f"{repo_base.rstrip('/')}/commit/{commit}"


class FindingOut(BaseModel):
    severity: str
    line_no: int | None = None
    text: str


class LogReportOut(BaseModel):
    source: str
    kernel_version: str | None = None
    board: str | None = None
    kernel_commit: str | None = None
    hdl_commit: str | None = None
    kernel_commit_url: str | None = None
    hdl_commit_url: str | None = None
    error_count: int
    warn_count: int
    has_panic: bool
    findings: list[FindingOut] = Field(default_factory=list)


class BootSummary(BaseModel):
    kernel_version: str | None = None
    board: str | None = None
    kernel_commit: str | None = None
    hdl_commit: str | None = None
    kernel_commit_url: str | None = None
    hdl_commit_url: str | None = None
    error_count: int = 0
    warn_count: int = 0
    has_panic: bool = False
    shared_kernel_count: int = 0
    shared_hdl_count: int = 0


class CommitCount(BaseModel):
    commit: str
    run_count: int
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_schemas_log.py -q --no-cov`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/prism_api/schemas/log.py apps/api/tests/test_schemas_log.py
git commit -m "feat(api): log report/boot-summary schemas + commit_url helper"
```

---

### Task 8: `GET /runs/{id}/logs` + boot summary on RunDetail

**Files:**

- Modify: `apps/api/src/prism_api/routers/runs.py`
- Modify: `apps/api/src/prism_api/schemas/run.py`
- Create helper: `apps/api/src/prism_api/services/boot_summary.py`
- Test: `apps/api/tests/test_logs_router.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_logs_router.py
import io, json, zipfile


def _login(client):
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    return client.cookies.get("prism_csrf") or ""


_BOOT = b"Linux version 6.1.0-g1a2b3c4 (j) #1\nHDL git hash: deadbeef1234\n<3> mmc0: error\n"


def _upload(client, csrf, name):
    junit = b'<?xml version="1.0"?><testsuites><testsuite name="s" tests="1" failures="0"><testcase classname="c" name="t"/></testsuite></testsuites>'
    arc = io.BytesIO()
    with zipfile.ZipFile(arc, "w") as zf:
        zf.writestr("boot.log", _BOOT)
    return client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", junit, "application/xml"),
               "archive": ("a.zip", arc.getvalue(), "application/zip")},
        data={"metadata": json.dumps({"project_slug": "rf", "name": name})},
        headers={"X-Prism-Csrf": csrf},
    ).json()["id"]


def test_run_logs_and_boot_summary(client, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "rf", "name": "RF"})
    run_id = _upload(client, csrf, "r1")

    logs = client.get(f"/api/v1/runs/{run_id}/logs").json()
    assert logs[0]["kernel_commit"] == "1a2b3c4"
    assert logs[0]["hdl_commit"] == "deadbeef1234"
    assert any(f["severity"] == "error" for f in logs[0]["findings"])

    detail = client.get(f"/api/v1/runs/{run_id}").json()
    assert detail["boot"]["kernel_commit"] == "1a2b3c4"
    assert detail["boot"]["error_count"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_logs_router.py -q --no-cov`
Expected: FAIL (404 on `/logs`; `detail["boot"]` KeyError).

- [ ] **Step 3: Implement boot-summary service + endpoint + RunDetail field**

```python
# apps/api/src/prism_api/services/boot_summary.py
"""Resolve a run's boot summary from its (possibly several) log reports."""

from prism_api.config import Settings
from prism_api.repos.logs import LogRepo
from prism_api.schemas.log import BootSummary, commit_url


def build_boot_summary(repo: LogRepo, run_id: str, settings: Settings) -> BootSummary | None:
    reports = repo.list_by_run(run_id)
    if not reports:
        return None

    def first(attr: str) -> str | None:
        for r in reports:  # oldest-first (list_by_run orders by created_at)
            v = getattr(r, attr)
            if v:
                return v
        return None

    kernel_commit = first("kernel_commit")
    hdl_commit = first("hdl_commit")
    return BootSummary(
        kernel_version=first("kernel_version"),
        board=first("board"),
        kernel_commit=kernel_commit,
        hdl_commit=hdl_commit,
        kernel_commit_url=commit_url(settings.kernel_repo_url, kernel_commit),
        hdl_commit_url=commit_url(settings.hdl_repo_url, hdl_commit),
        error_count=sum(r.error_count for r in reports),
        warn_count=sum(r.warn_count for r in reports),
        has_panic=any(r.has_panic for r in reports),
        shared_kernel_count=(
            repo.shared_count("kernel", kernel_commit, exclude_run_id=run_id)
            if kernel_commit else 0
        ),
        shared_hdl_count=(
            repo.shared_count("hdl", hdl_commit, exclude_run_id=run_id) if hdl_commit else 0
        ),
    )
```

In `apps/api/src/prism_api/schemas/run.py` add to `RunDetail`:

```python
    boot: "BootSummary | None" = None
```

and at the top import:

```python
from prism_api.schemas.log import BootSummary
```

(Place the import after the existing imports; `RunDetail` already extends `RunOut`.)

In `apps/api/src/prism_api/routers/runs.py`:

- imports:

```python
from prism_api.config import Settings
from prism_api.deps import get_settings_dep
from prism_api.repos.logs import LogRepo
from prism_api.schemas.log import FindingOut, LogReportOut, commit_url
from prism_api.services.boot_summary import build_boot_summary
```

- In `get_run`, accept settings and set `boot`. Change the signature to add `settings: Settings = Depends(get_settings_dep)` and build the summary:

```python
    boot = build_boot_summary(LogRepo(session), run.id, settings)
```

then pass `boot=boot` into the `RunDetail(...)` constructor.

- Add the logs endpoint:

```python
@router.get("/{run_id}/logs", response_model=list[LogReportOut])
def get_run_logs(
    run_id: str,
    _: User = Depends(current_user),
    settings: Settings = Depends(get_settings_dep),
    session: Session = Depends(session_dep),
) -> list[LogReportOut]:
    runs = RunRepo(session)
    if runs.get_by_id(run_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    repo = LogRepo(session)
    out: list[LogReportOut] = []
    for r in repo.list_by_run(run_id):
        out.append(
            LogReportOut(
                source=r.source,
                kernel_version=r.kernel_version,
                board=r.board,
                kernel_commit=r.kernel_commit,
                hdl_commit=r.hdl_commit,
                kernel_commit_url=commit_url(settings.kernel_repo_url, r.kernel_commit),
                hdl_commit_url=commit_url(settings.hdl_repo_url, r.hdl_commit),
                error_count=r.error_count,
                warn_count=r.warn_count,
                has_panic=r.has_panic,
                findings=[
                    FindingOut(severity=f.severity, line_no=f.line_no, text=f.text)
                    for f in repo.findings_for(r.id)
                ],
            )
        )
    return out
```

Note: `get_run` already takes `_` (user) and `session`; the existing direct call `get_run(run_id, user, session)` inside `set_calibration` must be updated to pass settings too — change it to `get_run(run_id, user, session, settings)` and add `settings: Settings = Depends(get_settings_dep)` to `set_calibration`'s signature.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_logs_router.py -q --no-cov`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/prism_api/services/boot_summary.py apps/api/src/prism_api/routers/runs.py \
  apps/api/src/prism_api/schemas/run.py apps/api/tests/test_logs_router.py
git commit -m "feat(api): GET /runs/:id/logs and boot summary on run detail"
```

---

### Task 9: Commits endpoint + run filter by commit

**Files:**

- Modify: `apps/api/src/prism_api/routers/projects.py`
- Modify: `apps/api/src/prism_api/routers/runs.py`
- Modify: `apps/api/src/prism_api/repos/runs.py`
- Test: `apps/api/tests/test_commits_router.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_commits_router.py
import io, json, zipfile


def _login(client):
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    return client.cookies.get("prism_csrf") or ""


def _boot(kernel):
    return f"Linux version 6.1.0-g{kernel} (j) #1\nHDL git hash: deadbeef1234\n".encode()


def _upload(client, csrf, name, kernel):
    junit = b'<?xml version="1.0"?><testsuites><testsuite name="s" tests="1" failures="0"><testcase classname="c" name="t"/></testsuite></testsuites>'
    arc = io.BytesIO()
    with zipfile.ZipFile(arc, "w") as zf:
        zf.writestr("boot.log", _boot(kernel))
    return client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", junit, "application/xml"),
               "archive": ("a.zip", arc.getvalue(), "application/zip")},
        data={"metadata": json.dumps({"project_slug": "rf", "name": name})},
        headers={"X-Prism-Csrf": csrf},
    ).json()["id"]


def test_commits_listing_and_filter(client, seed_admin, patch_ingest) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "rf", "name": "RF"})
    _upload(client, csrf, "a", "1111111")
    _upload(client, csrf, "b", "1111111")
    _upload(client, csrf, "c", "2222222")

    commits = client.get("/api/v1/projects/rf/commits", params={"type": "kernel"}).json()
    by = {c["commit"]: c["run_count"] for c in commits}
    assert by == {"1111111": 2, "2222222": 1}

    runs = client.get("/api/v1/runs", params={"project": "rf", "kernel_commit": "1111111"}).json()
    assert sorted(r["name"] for r in runs) == ["a", "b"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_commits_router.py -q --no-cov`
Expected: FAIL (404 on `/commits`; `kernel_commit` filter ignored returns all 3).

- [ ] **Step 3: Implement**

In `apps/api/src/prism_api/repos/runs.py`, extend `list_with_filters` to accept commit filters by joining `LogReport`:

```python
from prism_api.models.log import LogReport  # add to imports
```

Add params `kernel_commit: str | None = None, hdl_commit: str | None = None` and inside, after the tag filter block:

```python
        if kernel_commit is not None:
            stmt = stmt.where(
                TestRun.id.in_(
                    select(LogReport.run_id).where(LogReport.kernel_commit == kernel_commit)
                )
            )
        if hdl_commit is not None:
            stmt = stmt.where(
                TestRun.id.in_(
                    select(LogReport.run_id).where(LogReport.hdl_commit == hdl_commit)
                )
            )
```

In `apps/api/src/prism_api/routers/runs.py` `list_runs`, add query params and pass through:

```python
    kernel_commit: str | None = Query(default=None),
    hdl_commit: str | None = Query(default=None),
```

and in the `runs.list_with_filters(...)` call add `kernel_commit=kernel_commit, hdl_commit=hdl_commit,`.

In `apps/api/src/prism_api/routers/projects.py` add the commits endpoint (near the tag-keys/values endpoints), with imports `from prism_api.repos.logs import LogRepo` and `from prism_api.schemas.log import CommitCount`:

```python
@router.get("/{slug}/commits")
def list_commits(
    slug: str,
    type: str = "kernel",
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[CommitCount]:
    p = _project_or_404(session, slug)
    if type not in ("kernel", "hdl"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "type must be kernel or hdl")
    return [
        CommitCount(commit=c, run_count=n)
        for c, n in LogRepo(session).commit_counts_for_project(type, p.id)
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_commits_router.py -q --no-cov`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/prism_api/repos/runs.py apps/api/src/prism_api/routers/runs.py \
  apps/api/src/prism_api/routers/projects.py apps/api/tests/test_commits_router.py
git commit -m "feat(api): project commits listing + runs filter by kernel/hdl commit"
```

---

### Task 10: Compare boot block

**Files:**

- Modify: `apps/api/src/prism_api/schemas/compare.py`
- Modify: `apps/api/src/prism_api/routers/compare.py`
- Test: `apps/api/tests/test_compare_router.py` (add a case)

- [ ] **Step 1: Write the failing test (append to existing file)**

```python
def test_compare_includes_boot_blocks(client, seed_admin, patch_ingest) -> None:
    import io, json, zipfile
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    csrf = client.cookies.get("prism_csrf") or ""
    client.post("/api/v1/projects", json={"slug": "rf", "name": "RF"})

    def up(name, kernel):
        junit = b'<?xml version="1.0"?><testsuites><testsuite name="s" tests="1" failures="0"><testcase classname="c" name="t"/></testsuite></testsuites>'
        arc = io.BytesIO()
        with zipfile.ZipFile(arc, "w") as zf:
            zf.writestr("boot.log", f"Linux version 6.1.0-g{kernel} (j) #1\n".encode())
        return client.post("/api/v1/runs",
            files={"junit": ("j.xml", junit, "application/xml"),
                   "archive": ("a.zip", arc.getvalue(), "application/zip")},
            data={"metadata": json.dumps({"project_slug": "rf", "name": name})},
            headers={"X-Prism-Csrf": csrf}).json()["id"]

    r1, r2 = up("a", "1111111"), up("b", "2222222")
    body = client.post("/api/v1/compare", json={"run_ids": [r1, r2]}).json()
    assert [b["kernel_commit"] for b in body["boots"]] == ["1111111", "2222222"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_compare_router.py::test_compare_includes_boot_blocks -q --no-cov`
Expected: FAIL (`KeyError: 'boots'`).

- [ ] **Step 3: Implement**

In `apps/api/src/prism_api/schemas/compare.py` add a per-run boot block and field on the response:

```python
from prism_api.schemas.log import BootSummary  # add import

# add to CompareResponse:
    boots: list[BootSummary | None] = Field(default_factory=list)
```

(If `Field` isn't imported there, import it from pydantic.)

In `apps/api/src/prism_api/routers/compare.py`, build the boots list in run order using the existing settings dependency (add `settings: Settings = Depends(get_settings_dep)` to the compare handler, and imports for `Settings`, `get_settings_dep`, `LogRepo`, `build_boot_summary`):

```python
    repo = LogRepo(session)
    boots = [build_boot_summary(repo, rid, settings) for rid in run_ids]
```

and pass `boots=boots` into the `CompareResponse(...)` construction. (`run_ids` is the ordered list already used to build `runs`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_compare_router.py -q --no-cov`
Expected: PASS (all compare tests).

- [ ] **Step 5: Run full backend gate + commit**

```bash
cd apps/api && uv run pytest -q --no-cov && uv run mypy src && uv run ruff check .
git add apps/api/src/prism_api/schemas/compare.py apps/api/src/prism_api/routers/compare.py apps/api/tests/test_compare_router.py
git commit -m "feat(api): per-run boot blocks in Compare response"
```

---

## Stage 3 — Web UI

### Task 11: Types + react-query hooks

**Files:**

- Modify: `apps/web/src/api/types.ts`
- Modify: `apps/web/src/api/queries.ts`

- [ ] **Step 1: Add types** (`apps/web/src/api/types.ts`)

```ts
export interface LogFinding {
  severity: 'error' | 'warn' | 'panic' | 'probe_fail';
  line_no: number | null;
  text: string;
}

export interface LogReport {
  source: string;
  kernel_version: string | null;
  board: string | null;
  kernel_commit: string | null;
  hdl_commit: string | null;
  kernel_commit_url: string | null;
  hdl_commit_url: string | null;
  error_count: number;
  warn_count: number;
  has_panic: boolean;
  findings: LogFinding[];
}

export interface BootSummary {
  kernel_version: string | null;
  board: string | null;
  kernel_commit: string | null;
  hdl_commit: string | null;
  kernel_commit_url: string | null;
  hdl_commit_url: string | null;
  error_count: number;
  warn_count: number;
  has_panic: boolean;
  shared_kernel_count: number;
  shared_hdl_count: number;
}

export interface CommitCount {
  commit: string;
  run_count: number;
}
```

Also add `boot: BootSummary | null;` to the existing `RunDetail` interface, and `boots: (BootSummary | null)[];` to `CompareResponse`.

- [ ] **Step 2: Add hooks** (`apps/web/src/api/queries.ts`)

```ts
export function useRunLogs(runId: string | undefined) {
  return useQuery({
    queryKey: ['runs', runId, 'logs'],
    queryFn: async () => (await api.get<LogReport[]>(`/runs/${runId}/logs`)).data,
    enabled: Boolean(runId),
  });
}

export function useCommits(projectSlug: string | undefined, type: 'kernel' | 'hdl') {
  return useQuery({
    queryKey: ['projects', projectSlug, 'commits', type],
    queryFn: async () =>
      (await api.get<CommitCount[]>(`/projects/${projectSlug}/commits`, { params: { type } })).data,
    enabled: Boolean(projectSlug),
  });
}

export function useRunsByCommit(
  projectSlug: string | undefined,
  field: 'kernel_commit' | 'hdl_commit',
  commit: string | undefined,
) {
  return useQuery({
    queryKey: ['runs', projectSlug, 'by-commit', field, commit ?? null],
    queryFn: async () =>
      (await api.get<RunListItem[]>('/runs', {
        params: { project: projectSlug!, [field]: commit! },
      })).data,
    enabled: Boolean(projectSlug) && Boolean(commit),
  });
}
```

Add `CommitCount`, `LogReport` (and `BootSummary` if referenced) to the `import type { … } from './types'` block.

- [ ] **Step 3: Verify + commit**

Run: `cd apps/web && npx tsc --noEmit && npm run lint`
Expected: clean.

```bash
git add apps/web/src/api/types.ts apps/web/src/api/queries.ts
git commit -m "feat(web): types + hooks for log reports, boot summary, commits"
```

---

### Task 12: Boot panel on RunDetail

**Files:**

- Create: `apps/web/src/components/BootPanel.tsx`
- Modify: `apps/web/src/pages/RunDetailPage.tsx`

- [ ] **Step 1: Write the component**

```tsx
// apps/web/src/components/BootPanel.tsx
import { Box, Flex, Text } from '@chakra-ui/react';

import { useRunLogs } from '../api/queries';
import type { BootSummary } from '../api/types';

const SEV_FG: Record<string, string> = {
  panic: 'var(--prism-status-fail-fg)',
  error: 'var(--prism-status-fail-fg)',
  probe_fail: 'var(--prism-status-warn-fg)',
  warn: 'var(--prism-status-warn-fg)',
};

function CommitLine({ label, commit, url, shared }: {
  label: string; commit: string | null; url: string | null; shared: number;
}) {
  if (!commit) return null;
  return (
    <Flex align="center" gap={2} fontSize="sm">
      <Text color="var(--prism-text-faint)" minW="48px">{label}</Text>
      {url ? (
        <a href={url} target="_blank" rel="noreferrer" style={{ color: 'var(--prism-link)', fontFamily: 'monospace' }}>
          {commit.slice(0, 12)}
        </a>
      ) : (
        <Text fontFamily="mono">{commit.slice(0, 12)}</Text>
      )}
      {shared > 0 && (
        <Text fontSize="xs" color="var(--prism-text-faint)">· {shared} other run{shared === 1 ? '' : 's'}</Text>
      )}
    </Flex>
  );
}

export function BootPanel({ runId, boot }: { runId: string; boot: BootSummary }) {
  const logs = useRunLogs(runId);
  return (
    <Box borderWidth={1} borderColor="var(--prism-border)" borderRadius="md" p={3} bg="var(--prism-bg-surface)">
      <Text fontSize="10px" textTransform="uppercase" letterSpacing="1px" color="var(--prism-text-faint)" mb={2}>
        Boot
      </Text>
      {boot.has_panic && (
        <Box mb={2} px={2} py={1} borderRadius="sm" bg="var(--prism-status-fail-bg)" color="var(--prism-status-fail-fg)" fontSize="sm" fontWeight="600">
          ✕ kernel panic detected
        </Box>
      )}
      {boot.kernel_version && <Text fontSize="sm">{boot.kernel_version}</Text>}
      {boot.board && <Text fontSize="xs" color="var(--prism-text-subtle)">{boot.board}</Text>}
      <Box mt={2}>
        <CommitLine label="kernel" commit={boot.kernel_commit} url={boot.kernel_commit_url} shared={boot.shared_kernel_count} />
        <CommitLine label="hdl" commit={boot.hdl_commit} url={boot.hdl_commit_url} shared={boot.shared_hdl_count} />
      </Box>
      <Text fontSize="xs" color="var(--prism-text-subtle)" mt={2}>
        {boot.error_count} errors · {boot.warn_count} warnings
      </Text>
      {logs.data && logs.data.some((r) => r.findings.length > 0) && (
        <Box mt={2} maxH="220px" overflowY="auto" fontFamily="mono" fontSize="xs">
          {logs.data.flatMap((r) => r.findings).map((f, i) => (
            <Text key={i} color={SEV_FG[f.severity] ?? 'var(--prism-text-muted)'} truncate>
              [{f.severity}] {f.text}
            </Text>
          ))}
        </Box>
      )}
    </Box>
  );
}
```

- [ ] **Step 2: Wire into RunDetail**

In `apps/web/src/pages/RunDetailPage.tsx`, import `BootPanel`, and inside `RunMetaPane` (the right pane), after the Status block, render the boot panel when present. The pane receives the run; add:

```tsx
{run.boot && (
  <Box mt={3}>
    <BootPanel runId={run.id} boot={run.boot} />
  </Box>
)}
```

(`run` is the `RunDetail` already passed to `RunMetaPane`; `BootSummary` type flows through `run.boot`.)

- [ ] **Step 3: Verify + commit**

Run: `cd apps/web && npx tsc --noEmit && npm run lint && npx vitest run`
Expected: clean; tests pass.

```bash
git add apps/web/src/components/BootPanel.tsx apps/web/src/pages/RunDetailPage.tsx
git commit -m "feat(web): boot panel (commits, version, findings) on run detail"
```

---

### Task 13: Commits tab on the dashboard

**Files:**

- Modify: `apps/web/src/pages/ProjectDashboardPage.tsx`

- [ ] **Step 1: Add the tab + component**

Add a `<Tabs.Trigger value="commits">Commits</Tabs.Trigger>` to the tab list and a matching `<Tabs.Content value="commits">{slug && <CommitsTab slug={slug} onFilter={(field, commit) => { setTab('runs'); /* see below */ }} />}</Tabs.Content>`.

Add a `commitFilter` state alongside `tagFilters` in `ProjectDashboardPage` to drive the runs list:

```tsx
const [commitFilter, setCommitFilter] = useState<{ field: 'kernel_commit' | 'hdl_commit'; commit: string } | null>(null);
```

When a commit is clicked, `setCommitFilter({ field, commit }); setTab('runs');`. In the Runs tab, when `commitFilter` is set, use `useRunsByCommit(slug, commitFilter.field, commitFilter.commit)` instead of the full `runsQuery.data` (render those rows; show a dismissible "filtered by <field> <commit>" chip that clears `commitFilter`).

`CommitsTab` component:

```tsx
function CommitsTab({ slug, onFilter }: {
  slug: string;
  onFilter: (field: 'kernel_commit' | 'hdl_commit', commit: string) => void;
}) {
  const kernel = useCommits(slug, 'kernel');
  const hdl = useCommits(slug, 'hdl');
  const section = (
    title: string, field: 'kernel_commit' | 'hdl_commit',
    data: { commit: string; run_count: number }[] | undefined,
  ) => (
    <Box mb={4}>
      <Text fontSize="10px" textTransform="uppercase" letterSpacing="1px" color="var(--prism-text-faint)" mb={1}>{title}</Text>
      {(!data || data.length === 0) && <Text fontSize="sm" color="var(--prism-text-subtle)">none</Text>}
      <Flex wrap="wrap" gap={2}>
        {(data ?? []).map((c) => (
          <Box as="button" key={c.commit} onClick={() => onFilter(field, c.commit)}
            px={2} py="2px" borderRadius="sm" borderWidth={1} fontSize="xs" fontFamily="mono" cursor="pointer"
            bg="var(--prism-bg-surface)" color="var(--prism-text-muted)" borderColor="var(--prism-border)">
            {c.commit.slice(0, 12)} <Text as="span" color="var(--prism-text-faint)">({c.run_count})</Text>
          </Box>
        ))}
      </Flex>
    </Box>
  );
  return <Box>{section('Kernel commits', 'kernel_commit', kernel.data)}{section('HDL commits', 'hdl_commit', hdl.data)}</Box>;
}
```

Import `useCommits`, `useRunsByCommit` from `../api/queries`.

- [ ] **Step 2: Verify + commit**

Run: `cd apps/web && npx tsc --noEmit && npm run lint && npx vitest run`
Expected: clean.

```bash
git add apps/web/src/pages/ProjectDashboardPage.tsx
git commit -m "feat(web): Commits tab + filter runs by kernel/hdl commit"
```

---

### Task 14: Compare boot block

**Files:**

- Modify: `apps/web/src/pages/ComparePage.tsx`

- [ ] **Step 1: Render the boot block**

After the `MeasurementDiffsTable` and before the case table, add a per-run boot row using `q.data.boots` aligned with `q.data.runs`:

```tsx
{q.data.boots?.some(Boolean) && (
  <Box overflowX="auto">
    <Table.Root variant="outline" size="sm">
      <Table.Header>
        <Table.Row>
          <Table.ColumnHeader>Run</Table.ColumnHeader>
          <Table.ColumnHeader>Kernel</Table.ColumnHeader>
          <Table.ColumnHeader>HDL</Table.ColumnHeader>
          <Table.ColumnHeader textAlign="end">Errors</Table.ColumnHeader>
          <Table.ColumnHeader textAlign="end">Warnings</Table.ColumnHeader>
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {q.data.runs.map((r, i) => {
          const b = q.data.boots[i];
          return (
            <Table.Row key={r.id}>
              <Table.Cell>{r.name}</Table.Cell>
              <Table.Cell fontFamily="mono">{b?.kernel_commit?.slice(0, 12) ?? '—'}</Table.Cell>
              <Table.Cell fontFamily="mono">{b?.hdl_commit?.slice(0, 12) ?? '—'}</Table.Cell>
              <Table.Cell textAlign="end">{b?.error_count ?? '—'}</Table.Cell>
              <Table.Cell textAlign="end">{b?.warn_count ?? '—'}</Table.Cell>
            </Table.Row>
          );
        })}
      </Table.Body>
    </Table.Root>
  </Box>
)}
```

- [ ] **Step 2: Verify + commit**

Run: `cd apps/web && npx tsc --noEmit && npm run lint && npx vitest run`
Expected: clean.

```bash
git add apps/web/src/pages/ComparePage.tsx
git commit -m "feat(web): per-run boot/commit block on Compare"
```

---

### Task 15: Web helper test + final gates

**Files:**

- Create: `apps/web/src/lib/logFindings.ts`
- Test: `apps/web/src/lib/logFindings.test.ts`

- [ ] **Step 1: Extract + test the severity-color map (pure helper)**

```ts
// apps/web/src/lib/logFindings.ts
export type Severity = 'error' | 'warn' | 'panic' | 'probe_fail';

export const SEVERITY_FG: Record<Severity, string> = {
  panic: 'var(--prism-status-fail-fg)',
  error: 'var(--prism-status-fail-fg)',
  probe_fail: 'var(--prism-status-warn-fg)',
  warn: 'var(--prism-status-warn-fg)',
};

export function severityColor(sev: string): string {
  return (SEVERITY_FG as Record<string, string>)[sev] ?? 'var(--prism-text-muted)';
}
```

```ts
// apps/web/src/lib/logFindings.test.ts
import { describe, expect, it } from 'vitest';
import { severityColor } from './logFindings';

describe('severityColor', () => {
  it('maps known severities and falls back', () => {
    expect(severityColor('panic')).toContain('fail');
    expect(severityColor('warn')).toContain('warn');
    expect(severityColor('unknown')).toContain('text-muted');
  });
});
```

Update `BootPanel.tsx` to import `severityColor` and drop its local `SEV_FG` map (DRY).

- [ ] **Step 2: Run the helper test**

Run: `cd apps/web && npx vitest run src/lib/logFindings.test.ts`
Expected: PASS.

- [ ] **Step 3: Full gates (api + web)**

Run:

```bash
cd apps/api && uv run pytest -q --no-cov && uv run mypy src && uv run ruff check .
cd ../web && npx tsc --noEmit && npm run lint && npx vitest run && npm run build
```

Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/lib/logFindings.ts apps/web/src/lib/logFindings.test.ts apps/web/src/components/BootPanel.tsx
git commit -m "feat(web): severity-color helper + test; final wiring"
```

---

## Self-review (completed by plan author)

- **Spec coverage:** parser (T1), tables/migration (T2), settings incl. repo URLs + cap (T3), repo + cross-ref queries (T4), ingest (T5), backfill CLI (T6), schemas + commit_url (T7), `/runs/:id/logs` + boot summary on RunDetail incl. shared counts (T8), commits listing + run filter by commit (T9), Compare boot blocks (T10), web types/hooks (T11), Boot panel with repo links + findings + shared-commit (T12), Commits tab + filter (T13), Compare UI block (T14), web helper test + final gates (T15). All four cross-ref behaviors and all four extraction categories are covered.
- **Severity precedence note:** implemented as panic > probe_fail > error > warn (the spec's listed order would make probe_fail unreachable because probe phrases contain "fail"); `error_count`/`warn_count` count only `error`/`warn` severities, panic sets `has_panic`, probe_fail is its own finding severity. This refinement is intentional and reflected in tests.
- **Type consistency:** `BootSummary`, `LogReport`, `LogReportOut`, `FindingOut`, `CommitCount`, `commit_url`, `build_boot_summary`, `LogRepo.commit_counts_for_project`, `shared_count` names are used identically across tasks.
- **Backfill caveat:** suite/case-scoped logs store the owner id in `run_id` (documented in T6); resolving the true run for non-run-scoped logs is explicitly out of scope.
