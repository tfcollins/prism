.PHONY: up down logs build test lint fmt docs clean

COMPOSE := docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml --env-file deploy/.env

up:
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

lint:
	cd apps/api && uv run ruff check . && uv run mypy src
	cd apps/web && npm run lint

fmt:
	cd apps/api && uv run ruff format .
	cd apps/web && npm run fmt

docs:
	cd docs && mkdocs serve

clean:
	$(COMPOSE) down -v
