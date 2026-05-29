<!-- markdownlint-disable-file MD041 -->
<p align="center">
  <img src="assets/logo.svg" alt="Prism logo" width="96" />
</p>

<h1 align="center">Prism</h1>

<p align="center">
  A self-hostable web app for managing, browsing, plotting, and cross-analyzing
  test results — JUnit XML plus measurement artifacts (waveforms, FFTs, logs).
</p>

## Quickstart

```bash
cp deploy/.env.example deploy/.env
make up
open http://localhost:8180
```

Default admin login and dev-mode host ports are set in `deploy/.env`. The defaults (`8180` for the web UI, `5433` for postgres, `6380` for redis, `9100/9101` for MinIO, `8000` for the api) are chosen to avoid collisions with locally installed services — override any of them in your `.env`. See the [getting-started tutorial](docs/source/tutorials/getting-started.md), or run `make docs` for the full rendered site.

## Repo layout

- `apps/api/` — FastAPI backend + Celery worker
- `apps/web/` — React frontend (Chakra UI v3)
- `deploy/` — docker-compose orchestration
- `docs/` — Sphinx site (adi-doctools "cosmic" theme, Diátaxis-organized)
- `scripts/` — `upload_run.py` (CI uploader), `seed_demo.py` (demo dataset)
- `assets/` — brand assets (logo)
