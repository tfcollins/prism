# Prism — Design Spec

**Date:** 2026-04-19
**Status:** Draft, approved through brainstorming
**Author:** Claude (with travisfcollins@gmail.com)

## 1. Purpose

**Prism** is a self-hostable web application for managing, browsing, plotting, and cross-analyzing test results — both structured outcomes (JUnit XML) and the measurement artifacts those tests produce (time-domain waveforms, FFTs, logs, images). The name comes from the FFT metaphor: a prism decomposes light into its component frequencies, just as the app decomposes test runs into their many views. Primary use case: engineering teams running automated test suites that produce both pass/fail verdicts *and* signal data, where current tools (CI dashboards, raw file shares) make it painful to compare results across builds, branches, or hardware revisions.

### Success criteria

- A CI job can `POST` a test run (JUnit + artifacts) and have it appear in the UI within seconds.
- Two or more runs can be overlaid on the same FFT/time-domain plot for visual regression inspection.
- A user can filter runs by project, tag, status, and time range and drill down to a specific failing case's attached waveform in ≤3 clicks from the dashboard.
- All services start with a single `docker compose up`.
- Test suite is green; linters pass; docs site builds.

## 2. Non-goals (v1)

- Real-time streaming ingest (batched uploads only).
- Multi-tenant organizations / per-org billing.
- Alerting or notifications on regressions.
- User-authored plot scripts / notebooks.
- Fine-grained RBAC — v1 has a flat user pool where every authenticated user can read and write everything.
- Mobile-first UX (desktop-first, mobile-tolerant).

## 3. Scope — what gets built

### 3.1 Services (all in `docker-compose.yml`)

| Service | Image / Build | Purpose |
|---|---|---|
| `web` | Local build, React + Vite | SPA served via nginx in prod, Vite dev server in dev |
| `api` | Local build, Python 3.12 / FastAPI | REST + file upload coordination |
| `worker` | Same image as `api`, Celery entrypoint | Parses JUnit, ingests waveforms, computes FFTs |
| `postgres` | `postgres:16` | Metadata DB |
| `minio` | `minio/minio:latest` | S3-compatible object storage |
| `redis` | `redis:7` | Celery broker + result cache |
| `docs` | `squidfunk/mkdocs-material` (dev only) | Live docs preview |

Dev profile adds hot-reload mounts. Prod profile builds immutable images and runs behind a single nginx reverse proxy.

### 3.2 Data model (PostgreSQL)

```
Project (1) ──< TestRun (1) ──< TestSuite (1) ──< TestCase
                  │                                    │
                  ├──< RunTag (k/v)                    │
                  └──< Artifact >─────────────────────┘
                          │
                          └──< DerivedArtifact (FFT cache, thumbnails)
```

Key fields:

- **Project**: `id`, `slug`, `name`, `description`, `created_at`
- **TestRun**: `id`, `project_id`, `name`, `status` (pass/fail/mixed/error), `started_at`, `finished_at`, `junit_artifact_id`, `created_by`
- **RunTag**: `run_id`, `key`, `value` — indexed `(key, value)` for fast filter
- **TestSuite**: `id`, `run_id`, `name`, `pass_count`, `fail_count`, `error_count`, `skip_count`, `duration_ms`
- **TestCase**: `id`, `suite_id`, `classname`, `name`, `status`, `duration_ms`, `failure_message`, `failure_trace`
- **Artifact**: `id`, `owner_type` (run/suite/case), `owner_id`, `kind` (enum), `filename`, `size_bytes`, `content_hash`, `storage_key`, `metadata_json`
- **DerivedArtifact**: `id`, `source_artifact_id`, `kind` (fft, thumbnail, etc.), `storage_key`, `params_hash`

Artifact `kind` enum: `junit_xml`, `waveform_csv`, `waveform_hdf5`, `waveform_npy`, `wav_audio`, `image_png`, `log_text`, `other_binary`.

### 3.3 Object storage layout (MinIO)

```
prism/
  raw/{content_hash[0:2]}/{content_hash}               # content-addressed originals
  runs/{run_id}/{artifact_id}-{filename}               # friendly symlink-style lookups
  derived/fft/{source_hash}-{params_hash}.npy          # FFT cache
  derived/thumbs/{source_hash}.png                     # plot thumbnails
```

Content-addressed storage means identical artifacts across runs dedupe automatically. The friendly `runs/` prefix is a reference, not a separate copy.

### 3.4 API surface (FastAPI, under `/api/v1`)

**Projects**
- `GET /projects` — list
- `POST /projects` — create
- `GET /projects/{slug}` — detail

**Runs**
- `GET /runs?project=&tags=&status=&from=&to=&limit=&cursor=` — paginated list
- `POST /runs` — multipart upload: JUnit XML + optional archive of artifacts + JSON metadata body
- `GET /runs/{id}` — detail with suites/cases summary
- `DELETE /runs/{id}` — soft delete

**Cases & artifacts**
- `GET /cases/{id}` — detail including attached artifacts
- `GET /artifacts/{id}` — metadata
- `GET /artifacts/{id}/download` — signed redirect to MinIO
- `GET /artifacts/{id}/waveform?downsample=N` — JSON samples for plotting
- `GET /artifacts/{id}/fft?window=&nfft=&overlap=` — JSON magnitude spectrum, cached

**Comparison**
- `POST /compare` — body: `{run_ids: [...], case_filter?: "..."}` → returns diff summary
- `GET /compare/waveforms?artifact_ids=...` — aligned multi-series payload

**Auth & users**
- `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`
- `GET /users`, `POST /users`, `DELETE /users/{id}`
- JWT in `httpOnly` cookie. A bootstrap user is created from `PRISM_ADMIN_EMAIL` / `PRISM_ADMIN_PASSWORD` env vars on the api container's first start; once at least one user exists, those env vars are ignored. Any authenticated user may create or delete other users — the v1 trust model is flat.

OpenAPI spec auto-generated by FastAPI; served at `/api/docs`.

### 3.5 Frontend (React + Vite + Chakra UI v3 + TypeScript)

**Routes**
- `/login`
- `/` → redirect to most recent project
- `/projects`
- `/projects/:slug` — project dashboard
- `/runs/:id` — run detail with test tree + plot panel
- `/runs/:id/cases/:caseId` — case-focused view
- `/compare?runs=a,b,c` — comparison view

**State**
- Server state: TanStack Query (one source of truth for API data)
- Local UI state: Chakra + React hooks; no global store needed for v1
- Form state: `react-hook-form` + `zod`

**Plotting**
- Plotly.js via `react-plotly.js` — proven support for time-series, FFT magnitude, log-scale axes, interactive zoom
- Waveform downsampling happens server-side; the frontend requests a target sample count based on viewport width
- FFT is computed server-side (Welch's method via scipy) and cached — frontend just renders

**Visual design**
- Dark theme default, light theme toggle in top bar
- Monospace font for IDs / hashes / SHAs
- Chakra's design tokens drive spacing and color; no raw CSS except in Plotly config

### 3.6 Ingest pipeline (Celery worker)

1. `POST /runs` writes raw upload to MinIO under content hash; creates `TestRun` in `pending` state; enqueues `ingest_run` task.
2. Worker pulls JUnit XML, parses with `junitparser`, writes `TestSuite` / `TestCase` rows.
3. If archive was uploaded, worker extracts it to a temp dir, identifies each file's `kind` from extension + magic bytes, links to the appropriate owner (by filename convention: `{suite}__{case}__{label}.{ext}`).
4. Worker marks run `status = pass|fail|mixed|error` and bumps `finished_at`.
5. FFT generation is lazy: first request for `/artifacts/{id}/fft?...` enqueues `compute_fft` with the params hash; subsequent calls with same params hit cache.

Failures at any stage set `status = error`, log to a run-scoped error log artifact, and surface in the UI.

## 4. Quality

### 4.1 Testing

- **Backend unit tests**: pytest + `pytest-asyncio`, run against a SQLite fixture for model tests, against a real Postgres testcontainer for integration tests.
- **Backend integration tests**: FastAPI `TestClient` hitting a test compose stack (postgres + minio + redis). Uploads real JUnit fixtures.
- **Worker tests**: fixture-driven; assert that ingesting a known JUnit + waveform produces expected DB rows and MinIO keys.
- **Frontend unit tests**: vitest + React Testing Library — component-level.
- **Frontend E2E**: Playwright — golden paths (login, upload, browse, compare) run against the full compose stack in CI.
- **Coverage target**: backend ≥ 85%, frontend ≥ 70%. Enforced in CI.

### 4.2 Linting / formatting

- Python: **ruff** (lint + format), **mypy** in strict mode on `api/` and `worker/`.
- TypeScript: **eslint** (typescript-eslint recommended + react-hooks), **prettier**.
- Pre-commit hook runs ruff, eslint, and prettier on staged files.

### 4.3 CI (GitHub Actions)

- `lint` job: ruff + eslint + mypy
- `test-backend` job: runs postgres + minio + redis service containers, runs pytest
- `test-frontend` job: vitest
- `e2e` job: `docker compose up -d`, waits for health, runs Playwright
- `build-images` job (on tag): builds & pushes `api` and `web` images to GHCR
- `docs` job: builds MkDocs and deploys to GitHub Pages on `main`

### 4.4 Documentation

- `docs/` directory, MkDocs Material site, sections:
  - **Getting started** — clone, `docker compose up`, first upload
  - **Architecture** — diagram + service responsibilities (sourced from this spec)
  - **Data model** — schema reference
  - **API reference** — embedded via `mkdocs-swagger-ui-tag` pulling the live OpenAPI spec
  - **CI integration** — example uploader scripts (curl, Python helper)
  - **Development** — local setup, running tests, contributing
- `README.md` at repo root: one-page overview + quickstart + links to docs site.

## 5. Repository layout

```
prism/
├── apps/
│   ├── api/                    # FastAPI service (also hosts Celery worker entrypoint)
│   │   ├── src/prism_api/
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   └── web/                    # React SPA
│       ├── src/
│       ├── tests/
│       ├── e2e/                # Playwright specs
│       ├── package.json
│       └── Dockerfile
├── deploy/
│   ├── docker-compose.yml      # base
│   ├── docker-compose.dev.yml  # hot-reload overrides
│   ├── docker-compose.prod.yml # prod overrides + nginx
│   └── nginx/
├── docs/
│   ├── mkdocs.yml
│   └── (markdown sources)
├── .github/workflows/
├── .gitignore                  # includes .superpowers/
├── .pre-commit-config.yaml
├── Makefile                    # thin wrapper: make up/down/test/lint/docs
└── README.md
```

## 6. Out-of-scope / deferred

- Webhook triggers from common CI platforms — defer to v2, REST upload is enough for v1.
- Custom DSP (filtering, windowing beyond Hann) — v1 supports: no window, Hann, Hamming; overlap 0 / 0.5; nfft auto or user-specified.
- On-prem SSO (SAML/OIDC) — v1 is username+password with JWT.
- Retention/archival policies — manual delete only in v1.

## 7. Open questions

None blocking. Items to revisit post-v1: streaming ingest, orgs/RBAC, notifications, retention policies.
