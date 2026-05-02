# Lint & Format Hardening — Design

**Status:** Approved
**Date:** 2026-05-02
**Scope:** `prism/` only (cross-repo work tracked under `../../test_capture/docs/superpowers/`)

## Context

Prism ships three Python deliverables (`apps/api`, `clients/python-pytest`, `scripts/`) and one TypeScript app (`apps/web`). Today's lint posture is:

| Surface | Tools | Gaps |
|---|---|---|
| `apps/api` | ruff (`E,F,I,B,UP,ASYNC,S,C4,SIM,RUF`) + mypy --strict | no `ruff format --check` in CI |
| `clients/python-pytest` | ruff (`E,F,I,B,UP,C4,SIM,RUF`) + mypy --strict + ruff format --check | no `ASYNC` or `S` rules — accidental drift from api |
| `scripts/` | none | no pyproject; `_prism_client.py` is vendored into pyadi-iio's prism-report plugin (downstream consumers expect lint-clean code) |
| `apps/web` | eslint (`max-warnings 0`) + prettier | no a11y plugin; no import-order rule |
| Cross-cutting (workflows YAML, markdown docs, Dockerfiles) | none | bit-rot has no automated check |

This spec defines a single coordinated PR-shaped change to close the gaps without introducing pre-commit hooks (CI remains the gate).

## Goal

Bring the repo to a uniform lint posture: identical Python rule sets across all three deliverables, accessibility lint on the frontend, and CI-gated linting for GitHub Actions YAML, markdown, and Dockerfiles. Existing violations are fixed as part of the work — no grandfathering.

## Out of scope (other lanes)

- Pre-commit hooks (explicitly declined).
- Testing hardening — `@axe-core/playwright` runtime a11y, coverage targets, more e2e flows. Belongs in the testing brainstorm.
- Documentation gaps — content authoring, contributor guide, renderer-authoring guide for `pytest-prism`. Belongs in the docs brainstorm.
- Webapp user-friendliness work.
- `gitleaks` / secret scanning — declined for this lane.
- `stylelint`, `shellcheck`, `yamllint`, `codespell` — low value for current surface, declined.

## Architecture

### Orchestration

No new orchestrator. The existing two-tier setup is extended:

- **Local:** `make lint` is the single entrypoint. It fans out to per-domain sub-targets:
  - Existing: `lint` runs api (`ruff check` + `mypy`) and web (`eslint`).
  - New sub-targets: `lint-md`, `lint-actions`, `lint-dockerfiles`. `make lint` runs all of them.
  - `lint-actions` and `lint-dockerfiles` skip with a visible notice (e.g., `actionlint not on PATH; skipping (CI will still run it)`) if the binary isn't installed — so contributors aren't forced to install Go for actionlint or Haskell-built hadolint locally, but a green local `make lint` is never silently incomplete.
- **CI:** `.github/workflows/lint.yml` gains three new jobs (`markdown`, `actions`, `dockerfile`) running in parallel with existing `api` and `web` jobs. Workflow finishes in the time of its slowest job, not the sum.

### No new top-level `pyproject.toml`

`scripts/` is linted by invoking `apps/api`'s ruff config from outside its directory:

```
cd apps/api && uv run ruff check ../../scripts && uv run ruff format --check ../../scripts
cd apps/api && uv run mypy ../../scripts
```

This is added to api's existing `lint.yml` job (one extra command, no new job needed).

## Per-lane changes

### Lane A — Python deliverable alignment

**`clients/python-pytest/pyproject.toml`:**
- `[tool.ruff.lint] select` becomes `["E","F","I","B","UP","ASYNC","S","C4","SIM","RUF"]` (api's full set, including `ASYNC` for uniformity even though the plugin is synchronous — adding rules with no matching code is inert).
- Test directory's existing per-file-ignores expanded to suppress `S101`/`S105`/`S106`/`S107` if not already covered.

**`apps/api/pyproject.toml`:**
- Rule set unchanged.
- CI gains `uv run ruff format --check .` (matching pytest-prism's CI step).

**`scripts/`:**
- Linted via api's pyproject as described in Architecture.
- mypy: included in api's mypy run. `_prism_client.py` is the vendored source for pyadi-iio's prism-report plugin (which is strict-mypy); keeping it type-clean here prevents downstream churn.

**Workflow file:** `.github/workflows/lint.yml`'s `api` job's command list extended to include the format check and the scripts/ commands. No new job for Python lane.

### Lane D — Frontend accessibility & import order

**Dependencies (`apps/web/package.json`):**
- `eslint-plugin-jsx-a11y` (latest 6.x, eslint v9 compatible).
- `eslint-plugin-simple-import-sort`.

**`apps/web/eslint.config.js`:**
- Extend `jsx-a11y/recommended` ruleset.
- Add `simple-import-sort/imports` and `simple-import-sort/exports` at severity `error`.
- Remove any existing import-order rule from the existing config to avoid conflict.

**One-shot fix commit:** `eslint --fix` run separately to bulk-apply import sort across all `.ts`/`.tsx` files. This is committed as a distinct commit from the rule additions for review clarity.

### Lane B — Cross-cutting linters

**actionlint** (GitHub Actions YAML):
- CI: new `actions` job in `lint.yml` using the official docker image (`rhysd/actionlint:latest`).
- Runs on `.github/workflows/*.yml`.
- Local: `make lint-actions` invokes `actionlint` from `PATH`; skips silently if missing.

**markdownlint** (`markdownlint-cli2`):
- New repo-root `package.json` + `package-lock.json` (NOT inside `apps/web/`) — markdownlint covers markdown across api, web, scripts, docs, and READMEs at the repo root.
- New `.markdownlint-cli2.jsonc` at repo root.
- Default ruleset, with these disables:
  - `MD013` (line-length) — too noisy for prose.
  - `MD033` (inline HTML) — needed for the existing `<p align="center">` logo block in `README.md`.
- Exclude paths: `node_modules/`, `site/`, `.venv/`, `apps/web/playwright-report/`, `apps/web/test-results/`, `apps/api/.venv/`, `clients/python-pytest/.venv/`.
- CI: new `markdown` job runs `npx markdownlint-cli2`.
- Local: `make lint-md`.

**hadolint** (Dockerfiles):
- CI: new `dockerfile` job using `hadolint/hadolint:latest-alpine` docker image.
- Runs against `apps/api/Dockerfile`, `apps/api/Dockerfile.dev`, `apps/web/Dockerfile`, `apps/web/Dockerfile.dev`.
- Local: `make lint-dockerfiles` invokes `hadolint` from `PATH`; skips silently if missing.

## Rollout — fix-as-part-of-lane

Existing violations are fixed inside this work, not grandfathered. Estimated cost: a few hours, single PR. Grandfathering machinery would outweigh the fix cost given this surface area.

### Sequencing (within the implementation plan)

1. **Scaffolding phase** — land orchestration: Makefile sub-targets, new `lint.yml` jobs, configuration files (`.markdownlint-cli2.jsonc`, root `package.json`). Each new CI job is initially marked `continue-on-error: true` so the workflow stays green during the fix-up phase.
2. **Fix phase** — clear violations per tool, in order of independence (each step is its own commit so reviewers can see each tool's findings separately):
   1. `hadolint` — Dockerfile fixes (typically pinning, `--no-install-recommends`, `apt-get` cache cleanup).
   2. `actionlint` — workflow fixes (typically version pins, expression typos).
   3. `markdownlint` — markdown fixes.
   4. ruff `S` rules on `clients/python-pytest` — expected zero or near-zero findings.
   5. ruff `format --check` on `apps/api` — likely a one-shot `ruff format .` run if any drift exists.
   6. mypy strict on `scripts/` — first time these files are type-checked; expect a small batch of annotation fixes (esp. in `upload_run.py` and `seed_demo.py`).
   7. `jsx-a11y` findings — Chakra v3 components handle most a11y already; expect 5–15 findings (missing `alt`, click-handlers without keyboard equivalents).
   8. `simple-import-sort` bulk fix — last, because it touches every TS file. Single `eslint --fix` commit.
3. **Gating phase** — flip each CI job from `continue-on-error: true` to gating, one at a time, as its violations are cleared. Final commit removes all `continue-on-error` flags.

## Success criteria

- `make lint` (with all binaries available locally) returns 0 across all five lanes.
- `.github/workflows/lint.yml` has 5 jobs, all gating (no `continue-on-error`).
- `clients/python-pytest`'s `[tool.ruff.lint] select` byte-equals `apps/api`'s.
- `scripts/` is linted (ruff check + format) and type-checked (mypy strict) by the api's lint job.
- `apps/web/eslint.config.js` references `jsx-a11y/recommended` and `simple-import-sort` plugins.
- `apps/web` build (`npm run build`) and tests (`npm test`) still pass after the bulk import sort.

## Risks

- **eslint v9 flat-config compatibility:** `eslint-plugin-jsx-a11y` 6.x is the version line that supports flat config. Verify version pin during implementation.
- **Existing CI auto-merge / branch-protection rules** may need updating to require the three new jobs after they're flipped to gating. Out of scope for this spec; flagged for the implementer.
- **Root `package.json` introduction** is a new top-level surface — keep it minimal (markdownlint only); resist using it as a kitchen sink. If a contributor adds another dev tool here later, that's a separate decision.
