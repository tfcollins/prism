# Architecture

Prism ships as a docker-compose stack of seven services. The browser talks only
to `web` (nginx serving the React SPA) and `api`; everything else is internal.

```{mermaid}
flowchart LR
    Browser[Browser] --> Web[web<br/>nginx + React SPA]
    Web --> API[api<br/>FastAPI]
    API <--> PG[(postgres)]
    API <--> Redis[(redis<br/>broker)]
    Redis <--> Worker[worker<br/>Celery]
    API --> MinIO[(minio<br/>S3 blobs)]
    Worker --> MinIO
```

## Services

| Service | Tech | Responsibility |
|---|---|---|
| `web` | React + Vite + Chakra UI v3 | SPA: login, browse runs, plots, compare |
| `api` | FastAPI + SQLAlchemy | REST + auth + upload coordination |
| `worker` | Celery | JUnit parsing, archive extraction, FFT computation |
| `postgres` | Postgres 16 | Metadata: projects, runs, suites, cases, artifacts, users |
| `minio` | MinIO | Raw artifact bytes (content-addressed) + derived FFT cache |
| `redis` | Redis 7 | Celery broker + result backend |

## Backend module layout

Inside `apps/api/src/prism_api/`:

- `main.py` — FastAPI app + router wiring
- `routers/` — HTTP layer (auth, users, projects, runs, suites, cases, artifacts, compare)
- `repos/` — SQLAlchemy data access; routers never query directly
- `models/` — SQLAlchemy ORM (declarative, `models.base.Base`)
- `parsers/` — JUnit, waveform, filename, kind detection
- `dsp/` — waveform downsampling + FFT (numpy/scipy)
- `worker/` — `celery_app` + `tasks`; `prism.ingest_run` is the only task
- `migrations/` — Alembic
- `bootstrap.py` / `cli.py` — `prism-api bootstrap-admin` and `ensure-bucket`,
  invoked from `docker-entrypoint.sh` on container start

## Frontend module layout

Inside `apps/web/src/`:

- `pages/` — top-level routes (Projects, ProjectDashboard, RunDetail, Compare, Login)
- `routes/ProtectedRoute.tsx` — auth gate
- `api/` — axios client + react-query hooks + generated types
- `components/` — `RunsTable`, `TestTree`, `WaveformPlot`, `FFTPlot`, overlay variants, `AppShell`
- `auth/` — context + hook for the logged-in user
- `theme.ts` / `ColorModeProvider.tsx` — Chakra v3 theme + dark mode

## Authentication

Login sets two cookies: the JWT session and `prism_csrf` (the CSRF token). All
state-changing requests must echo the CSRF cookie back as the `X-Prism-Csrf`
header — a double-submit pattern. `scripts/upload_run.py` handles this
automatically; see {doc}`../how-to/upload-raw-http` for the raw shape.
