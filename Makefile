.PHONY: up up-bare down logs build test test-api test-web lint lint-api lint-web lint-md lint-actions lint-dockerfiles fmt fmt-api fmt-web docs clean

COMPOSE := docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml --env-file deploy/.env

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

test: test-api test-web

test-api:
	cd apps/api && uv run pytest

test-web:
	cd apps/web && npm test

lint: lint-api lint-web lint-md lint-actions lint-dockerfiles

lint-api:
	cd apps/api && uv run ruff check . && uv run mypy src

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
		hadolint apps/api/Dockerfile apps/api/Dockerfile.dev apps/web/Dockerfile apps/web/Dockerfile.dev; \
	else \
		echo "hadolint not on PATH; skipping (CI will still run it)"; \
	fi

fmt: fmt-api fmt-web

fmt-api:
	cd apps/api && uv run ruff format .

fmt-web:
	cd apps/web && npm run fmt

docs:
	cd docs && mkdocs serve

clean:
	$(COMPOSE) down -v
