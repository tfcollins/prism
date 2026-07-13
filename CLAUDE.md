# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Prism is a self-hostable web app for managing, browsing, plotting, and cross-analyzing test results — JUnit XML plus measurement artifacts (waveforms, FFTs, logs). It ships as a docker-compose stack with three first-party packages:

- `apps/api/` — FastAPI backend + Celery worker (Python 3.12, `uv`-managed, strict `mypy`)
- `apps/web/` — React 18 + Vite + Chakra UI v3 SPA (TypeScript)
- `clients/python-pytest/` — `pytest-prism` plugin (separately published, Python 3.10+, has its own `uv.lock`)

## Common commands

All-in-one via `Makefile` from the repo root:

```bash
make up              # bring stack up (auto-restarts web to defeat bind-mount race; see Makefile note)
make up-bare         # same as `up` but skip the restart (use if you've verified you don't hit the race)
make down            # stop stack
make clean           # `down -v` — wipes volumes
make logs            # docker compose logs -f
make test            # test-api + test-web
make lint            # ruff + mypy --strict (api), eslint (web), markdownlint, actionlint, hadolint
make fmt             # ruff format (api), prettier (web)
make docs            # sphinx-autobuild live preview (adi-doctools "cosmic" theme)
```

Stack uses `deploy/docker-compose.yml` + `deploy/docker-compose.dev.yml` with `deploy/.env` (copy from `.env.example`). First-time setup requires editing `deploy/.env` to set `JWT_SECRET` (≥32 chars, validated at startup) and `ADMIN_PASSWORD`. Host ports default to non-standard values (`8180` web, `8000` api, `5433` pg, `6380` redis, `9100/9101` minio) to avoid local collisions — override in `.env`.

### Backend (apps/api)

```bash
cd apps/api
uv sync --group dev                              # install deps incl. dev
uv run pytest                                    # full suite (xdist parallel, coverage on)
uv run pytest tests/test_runs_router.py          # single file
uv run pytest tests/test_runs_router.py::test_x  # single test
uv run pytest -k pattern                         # by name pattern
uv run ruff check . && uv run mypy src           # lint (matches CI)
uv run alembic revision --autogenerate -m "..."  # new migration; review then `alembic upgrade head`
```

Tests run with `pytest-xdist` (`-n auto`), `pytest-randomly`, and coverage by default — all configured in `pyproject.toml`. SQLite (in-memory) is used as the test DB via fixtures in `tests/conftest.py`; S3 is mocked with `moto`. `filterwarnings = ["error"]` is set, so any new deprecation must be addressed or explicitly silenced.

### Frontend (apps/web)

```bash
cd apps/web
npm install
npm run dev          # vite (only useful outside the compose stack)
npm test             # vitest run (unit)
npm run test:watch
npm run lint         # eslint --max-warnings 0
npm run build        # tsc --noEmit + vite build (also runs in CI)
npm run e2e          # playwright; needs stack up + seed_demo.py run
```

Playwright `baseURL` is `http://localhost:8180`; override with `PLAYWRIGHT_BASE_URL`. Auth in e2e reads `PLAYWRIGHT_ADMIN_EMAIL` / `PLAYWRIGHT_ADMIN_PASSWORD`. E2E asserts no serious/critical axe (a11y) violations.

### Run a single test in CI parity

CI workflows live in `.github/workflows/` (`lint.yml`, `test-backend.yml`, `test-frontend.yml`, `e2e.yml`, `docs.yml`, `pytest-prism.yml`). They invoke the same `uv run pytest` / `npm test` / `npm run e2e` commands above, so reproducing a CI failure locally is just running the matching command.

## Architecture (the parts that span files)

```text
Browser ──► web (nginx → React SPA) ──► api (FastAPI) ──► postgres
                                            │  ▲
                                            ▼  │
                                          redis ◄──► worker (Celery)
                                            │
                                            ▼
                                          minio (S3) — content-addressed blobs
```

**Ingest is async.** `POST /api/v1/runs` writes a `TestRun(status=pending)`, uploads bytes to MinIO under sha256-keyed paths, then dispatches `prism.ingest_run` to Celery via Redis. The worker (in `prism_api.worker.tasks`) parses JUnit with `junitparser`, walks the optional zip archive, identifies each file's kind via magic bytes + extension (`prism_api.parsers.detect`), and attaches it to the run/suite/case via the filename convention `{suite}__{case}__{label}.{ext}`. The run's status flips to pass/fail/mixed/error when done. Tests can run ingest inline (no broker) via the `patch_ingest` fixture in `tests/conftest.py`.

**Canonical shape: one JUnit upload == one `TestRun` == one `TestSuite`.** Multi-suite uploads are accepted (each `<testsuite>` becomes a row under the same run) but the dashboard assumes the one-suite form. See `docs/source/reference/data-model.md`.

**Artifacts are content-addressed and polymorphic.** The `artifacts` table has an `owner_type` discriminator (run / suite / case) instead of three FK columns. Identical bytes across runs share a single MinIO object. `DerivedArtifact` is a cache table keyed by `(source_hash, params_hash)` for computed views — the FFT endpoint (`GET /api/v1/artifacts/:id/fft`) reads this cache, computes Welch FFT and stores `.npz` on a miss. Waveform downsampling (`GET .../waveform?downsample=N`) is computed on the fly from `prism_api.dsp.downsample`.

**Two auth paths: cookie JWT (browser) and bearer API tokens (programmatic).** Browser login sets two cookies — the JWT session and `prism_csrf` (CSRF token); all cookie-based state-changing requests must echo the CSRF cookie back as the `X-Prism-Csrf` header. Programmatic clients (CI, scripts) instead send `Authorization: Bearer <token>` — per-user API tokens minted at `/api/v1/tokens` (managed in the web `TokensPage`); bearer requests skip CSRF entirely (`deps.csrf_protect`). `scripts/upload_run.py` supports both (`--token`/`PRISM_TOKEN` or `--email`/`--password`); raw `curl` examples in `docs/source/how-to/upload-raw-http.md` show the cookie pattern. **Optional LDAP** (search + bind) augments local password auth when `PRISM_LDAP_ENABLED=true` (see `ldap_auth.py` + `ldap_*` settings in `config.py`).

**Settings layer.** All runtime config is `PRISM_*` env vars consumed by `prism_api.config.Settings` (pydantic-settings). `get_settings()` is `lru_cache`d. In tests, override via the `settings` fixture and dependency overrides (`app.dependency_overrides[get_settings_dep]` in `conftest.py`).

**Module layout inside `apps/api/src/prism_api/`:**

- `main.py` — FastAPI app + router wiring
- `routers/` — HTTP layer (auth, users, projects, runs, suites, cases, artifacts, compare, admin, overview, search, tokens)
- `repos/` — SQLAlchemy data access; routers never query directly
- `schemas/` — pydantic request/response models (one module per domain)
- `models/` — SQLAlchemy ORM (declarative, `models.base.Base`)
- `parsers/` — JUnit, waveform, filename, kind detection
- `dsp/` — waveform downsampling + FFT (numpy/scipy)
- `reports/` — PDF generation via `fpdf2` (`run_report`, `compare_report`, `combined_report`); tests read PDFs back with `pypdf` to assert rendered text, not just `%PDF` magic bytes
- `services/` — cross-cutting logic (`retention`, `boot_summary`, `container_logs`)
- `worker/` — `celery_app` + `tasks`; `prism.ingest_run` is the only Celery task
- `auth.py` / `tokens.py` / `ldap_auth.py` — JWT encode/decode, API-token hashing, LDAP bind
- `ingest.py` — ingest logic invoked by the worker task (importable for inline test runs)
- `deps.py` — FastAPI dependencies (`current_user`, `csrf_protect`, `session_dep`)
- `storage.py` / `db.py` / `config.py` — MinIO/S3 client, SQLAlchemy engine/session, `PRISM_*` settings
- `migrations/` — Alembic
- `bootstrap.py` / `cli.py` — `prism-api bootstrap-admin` and `ensure-bucket` invoked from `docker-entrypoint.sh` on container start

**Module layout inside `apps/web/src/`:**

- `pages/` — top-level routes (Projects, ProjectDashboard, RunDetail, Compare, Overview, Search, Admin, Tokens, Login)
- `routes/ProtectedRoute.tsx` — auth gate
- `api/` — axios client + react-query hooks + generated types
- `components/` — `RunsTable`, `TestTree`, `WaveformPlot`, `FFTPlot`, overlay variants, `AppShell`
- `auth/` — context + hook for the logged-in user
- `theme.ts` / `ColorModeProvider.tsx` — Chakra v3 theme + dark mode

## Conventions worth knowing

- **`make up` restarts the web container.** Docker can race the bind-mount of `apps/web/src` into the container; if Vite starts before the mount lands, it caches an empty `/app/src` and 404s every `/src/*` request. The `Makefile` `up` target runs `docker compose restart web` after `up -d` to defeat this deterministically. If you've already verified your environment doesn't hit it, use `make up-bare`.
- **Strict mypy.** `apps/api` runs `mypy --strict` with `warn_unreachable = true`. Untyped third-party libs (celery, h5py, boto3, scipy) are suppressed at the import boundary in `pyproject.toml`; do not add blanket `# type: ignore` to your own code.
- **Coverage is on by default for pytest.** Running `uv run pytest` produces `htmlcov/` and `coverage.xml`. Use `--no-cov` if you need fast iteration.
- **`pytest.ini` filters warnings to errors,** with explicit allow-listed deprecations for passlib/jose internals and SQLAlchemy `Test*`-prefixed model classes (these are domain names, not test classes).
- **`scripts/upload_run.py` is stdlib-only Python 3** by design — CI can run it without `pip install`. If you touch it, don't add third-party deps.
- **CI uploads to Prism on every run** (`docs/source/how-to/ci-integration.md`); the canonical command and exit codes are documented there.
