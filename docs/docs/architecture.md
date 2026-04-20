# Architecture

```
┌─────────┐     ┌──────┐     ┌──────────┐     ┌──────────┐
│ Browser │────▶│ web  │────▶│   api    │◀───▶│ postgres │
└─────────┘     │nginx │     │ FastAPI  │     └──────────┘
                └──────┘     └──────────┘
                                  │  ▲
                                  ▼  │
                              ┌──────────┐    ┌─────────┐
                              │  redis   │◀──▶│ worker  │
                              │  broker  │    │ Celery  │
                              └──────────┘    └─────────┘
                                  │                │
                                  ▼                ▼
                              ┌──────────────────────┐
                              │     minio (S3)       │
                              └──────────────────────┘
```

## Services

| Service  | Tech                        | Responsibility |
|----------|-----------------------------|----------------|
| `web`    | React + Vite + Chakra UI v3 | SPA: login, browse runs, plots, compare |
| `api`    | FastAPI + SQLAlchemy        | REST + auth + upload coordination |
| `worker` | Celery                      | JUnit parsing, archive extraction, FFT computation |
| `postgres` | Postgres 16                | Metadata: projects, runs, suites, cases, artifacts, users |
| `minio`  | MinIO                        | Raw artifact bytes (content-addressed) + derived FFT cache |
| `redis`  | Redis 7                      | Celery broker + result backend |

## Data flow on upload

1. Browser POSTs `multipart/form-data` to `api`: junit XML + optional zip + JSON metadata. The `X-Prism-Csrf` header must match the `prism_csrf` cookie issued at login.
2. `api` writes a `TestRun(status=pending)` row, uploads the JUnit XML and (if present) zip to MinIO under content-addressed keys, dispatches `prism.ingest_run` to Celery via Redis.
3. `worker` pulls the task, fetches blobs from MinIO, parses JUnit (`junitparser`), extracts the zip, identifies each file's kind via magic bytes + extension, attaches each to its run/suite/case via the `{suite}__{case}__{label}` filename convention, and sets the run's final `status` (pass/fail/mixed/error).
4. Browser polls `GET /api/v1/runs/:id` to see the status flip from `pending`.

## Data flow on plot view

1. Browser navigates to a case → calls `GET /api/v1/cases/:id`, sees its attached `Artifact` rows.
2. For a waveform artifact, browser calls `GET /api/v1/artifacts/:id/waveform?downsample=N`. The api fetches the raw bytes from MinIO, parses with the right loader, runs `downsample_for_plot`, returns JSON samples.
3. For an FFT, browser calls `GET /api/v1/artifacts/:id/fft?window=&nfft=&overlap=`. The api looks up `DerivedArtifact` by `(source_hash, params_hash)`. Cache hit → load `.npz` from MinIO. Cache miss → compute Welch FFT, store as `.npz`, create `DerivedArtifact` row, return JSON.
