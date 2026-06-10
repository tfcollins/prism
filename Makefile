.PHONY: up up-bare down logs build deploy deploy-down deploy-logs test test-api test-web lint lint-api lint-client lint-web lint-md lint-actions lint-dockerfiles lint-docs fmt fmt-api fmt-web docs docs-build docs-venv docs-shots backup clean

# Local virtualenv for building the Sphinx docs (adi-doctools "cosmic" theme).
DOCS_VENV := docs/.venv
DOCS_PY := $(DOCS_VENV)/bin/python

COMPOSE := docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml --env-file deploy/.env

# Production stack: base compose + the prod overlay (publishes the web port,
# uses the built nginx/uvicorn images — no Vite, no bind mounts). Intended for a
# self-hosted host (e.g. a Raspberry Pi). See deploy/docker-compose.prod.yml.
PROD_COMPOSE := docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml --env-file deploy/.env

# `make up` brings the stack online and restarts the web container after the
# initial start. Docker can race the bind mount of apps/web/src into the
# container, and if vite happens to start before the mount lands it caches
# an empty /app/src and 404s every /src/* request until restarted. The extra
# `restart web` (a few seconds) makes `make up` deterministic. If you have
# already verified your environment doesn't hit the race, use `make up-bare`.
up:
	$(COMPOSE) up -d
	@echo "→ restarting web to defeat the bind-mount race (see Makefile up:)"
	@$(COMPOSE) restart web

up-bare:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

build:
	$(COMPOSE) build

# Production deploy (build images + start detached). Run on the host.
# GIT_COMMIT is baked into the web bundle (shown in the sidebar); compose reads
# it from the environment (see deploy/docker-compose.yml web build args).
deploy:
	GIT_COMMIT=$$(git rev-parse --short HEAD) $(PROD_COMPOSE) up -d --build

deploy-down:
	$(PROD_COMPOSE) down

deploy-logs:
	$(PROD_COMPOSE) logs -f

test: test-api test-web

test-api:
	cd apps/api && uv run pytest

test-web:
	cd apps/web && npm test

lint: lint-api lint-client lint-web lint-md lint-actions lint-dockerfiles lint-docs

# Mirrors the lint/type-check steps in .github/workflows/pytest-prism.yml for
# the separately-published pytest-prism client (its own uv environment).
lint-client:
	cd clients/python-pytest && uv sync --extra dev && \
		uv run ruff check . && uv run ruff format --check . && \
		uv run mypy src/pytest_prism tests

# Mirrors the api job in .github/workflows/lint.yml so `make lint-api`
# reproduces CI exactly: ruff lint + format-check + mypy across apps/api,
# scripts/, and docs/ (docs is ruff-only — see lint.yml for why).
lint-api:
	cd apps/api && \
		uv run ruff check . && uv run ruff format --check . && uv run mypy src && \
		uv run ruff check ../../scripts && uv run ruff format --check ../../scripts && uv run mypy ../../scripts && \
		uv run ruff check ../../docs && uv run ruff format --check ../../docs

lint-web:
	cd apps/web && npm run lint

lint-md:
	npx markdownlint-cli2 "**/*.md"

lint-actions:
	@if command -v actionlint >/dev/null 2>&1; then \
		actionlint .github/workflows/*.yml; \
	else \
		echo "actionlint not on PATH; skipping (CI will still run it)"; \
	fi

lint-dockerfiles:
	@if command -v hadolint >/dev/null 2>&1; then \
		hadolint apps/api/Dockerfile apps/api/Dockerfile.dev apps/web/Dockerfile apps/web/Dockerfile.dev deploy/backup/Dockerfile; \
	else \
		echo "hadolint not on PATH; skipping (CI will still run it)"; \
	fi

fmt: fmt-api fmt-web

fmt-api:
	cd apps/api && uv run ruff format .

fmt-web:
	cd apps/web && npm run fmt

# Create/refresh the docs build virtualenv from docs/requirements.txt.
docs-venv:
	@test -d $(DOCS_VENV) || uv venv $(DOCS_VENV) --python 3.12
	@uv pip install --python $(DOCS_PY) -r docs/requirements.txt

# Live-reloading preview of the Sphinx docs on http://localhost:8000.
docs: docs-venv
	$(DOCS_VENV)/bin/sphinx-autobuild docs/source docs/build/html

# One-shot strict build (warnings are errors) — what CI runs.
docs-build: docs-venv
	$(DOCS_VENV)/bin/sphinx-build -b html -W --keep-going docs/source docs/build/html

# Lint the docs: a strict Sphinx build catches broken refs, bad toctrees,
# unknown directives and MyST syntax errors as hard failures.
lint-docs: docs-venv
	$(DOCS_VENV)/bin/sphinx-build -b html -W --keep-going -q docs/source docs/build/html

# Recapture the UI screenshots embedded in the docs. Requires a running,
# seeded stack (see docs/source/tutorials/getting-started.md) and Playwright.
docs-shots: docs-venv
	uv pip install --python $(DOCS_PY) playwright
	$(DOCS_VENV)/bin/playwright install chromium
	$(DOCS_PY) docs/shots.py

# Run a single backup now (Postgres + MinIO → Cloudsmith), instead of waiting
# for the schedule. Honors deploy/.env; with no CLOUDSMITH_API_KEY it dumps
# locally and skips the upload (a useful dry run).
backup:
	$(COMPOSE) --profile backup run --rm -e BACKUP_RUN_ONCE=1 backup

clean:
	$(COMPOSE) down -v
