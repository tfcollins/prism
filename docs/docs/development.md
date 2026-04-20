# Development

## Local setup

```bash
# Backend
cd apps/api
uv sync --group dev
uv run pytest -v

# Frontend
cd apps/web
npm install
npm test
npm run build
```

## Running just the dependencies

If you want to run `uvicorn` directly (faster reload than docker rebuilds):

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml --env-file deploy/.env up -d postgres redis minio
PRISM_DATABASE_URL=postgresql+psycopg://prism:...@localhost:5433/prism \
PRISM_S3_ENDPOINT=http://localhost:9100 \
PRISM_S3_ACCESS_KEY=prism PRISM_S3_SECRET_KEY=... \
PRISM_S3_BUCKET=prism PRISM_REDIS_URL=redis://localhost:6380/0 \
PRISM_JWT_SECRET=dev-only-replace-with-32-plus-random-chars-please \
uv run uvicorn prism_api.main:app --reload
```

## Quality gates

`make lint` runs `ruff` + `mypy --strict` + `eslint`. CI runs the same on every PR.

## Adding a migration

```bash
cd apps/api
uv run alembic revision --autogenerate -m "describe change"
# Review/edit the generated file, then:
uv run alembic upgrade head
```
