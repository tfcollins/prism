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
