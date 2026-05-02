# Lint & Format Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the prism repo to a uniform lint posture across its three Python deliverables and one TypeScript app, plus add CI-gated linting for GitHub Actions YAML, markdown docs, and Dockerfiles.

**Architecture:** No pre-commit hooks; CI is the gate. Existing `make lint` is extended with sub-targets that fan out to per-domain linters. `.github/workflows/lint.yml` gains three new jobs (markdown, actions, dockerfile) running in parallel with the existing api/web jobs. New CI jobs initially run with `continue-on-error: true` while violations are fixed; the final task flips them to gating. No new top-level `pyproject.toml` — `scripts/` is linted by invoking `apps/api`'s ruff config from outside its directory.

**Tech Stack:** ruff, mypy, eslint v9 (flat config), markdownlint-cli2, actionlint, hadolint, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-05-02-prism-lint-hardening-design.md`

**Commit style (matches repo conventions):**

- `lint:` for cross-cutting tooling (markdownlint, actionlint, hadolint, Makefile, shared CI)
- `pytest-prism:` for `clients/python-pytest/` changes
- `prism-api:` for `apps/api/` (and `scripts/`) changes
- `prism-web:` for `apps/web/` changes
- All commits append `(Task N)` matching the task number in this plan
- No `Co-Authored-By` lines (per `no-co-author` skill)

**Branch:** all work lands on the current `tfcollins/dev` branch unless directed otherwise. Push once after each task to let CI exercise each step.

---

## File map

**Created:**

- `package.json` (repo root) — markdownlint-cli2 devDep
- `package-lock.json` (repo root)
- `.markdownlint-cli2.jsonc` (repo root)
- `node_modules/` (repo root, gitignored)

**Modified:**

- `Makefile` — new sub-targets: `lint-api`, `lint-web`, `lint-md`, `lint-actions`, `lint-dockerfiles`; `lint` aggregates them.
- `.github/workflows/lint.yml` — extend `api` job; add `markdown`, `actions`, `dockerfile` jobs.
- `clients/python-pytest/pyproject.toml` — ruff `select` aligned with api; add `[tool.ruff.lint.per-file-ignores]` and `ignore` lists.
- `apps/web/package.json` + `apps/web/package-lock.json` — add `eslint-plugin-jsx-a11y` and `eslint-plugin-simple-import-sort`.
- `apps/web/eslint.config.js` — wire the two new plugins.
- `apps/api/Dockerfile`, `apps/api/Dockerfile.dev`, `apps/web/Dockerfile`, `apps/web/Dockerfile.dev` — hadolint fixes.
- `.github/workflows/*.yml` — actionlint fixes.
- `**/*.md` — markdownlint fixes.
- `apps/web/src/**/*.{ts,tsx}` — jsx-a11y fixes + simple-import-sort bulk reorder.
- `scripts/*.py` — ruff fixes (likely none) + mypy annotations.

---

## Phase 1 — Scaffolding (non-breaking; new CI jobs land with `continue-on-error: true`)

### Task 1: Set up markdownlint at repo root + Makefile sub-targets

**Files:**

- Create: `package.json`, `package-lock.json`, `.markdownlint-cli2.jsonc`
- Modify: `Makefile`

- [ ] **Step 1: Initialize a minimal root `package.json`**

Create `package.json` at the repo root (NOT inside `apps/web/`):

```json
{
  "name": "prism-repo-tooling",
  "private": true,
  "description": "Repo-root dev tooling (markdownlint). Not a published package.",
  "devDependencies": {
    "markdownlint-cli2": "^0.13.0"
  }
}
```

- [ ] **Step 2: Install markdownlint-cli2 at the root**

Run from the repo root:

```bash
npm install
```

Expected: creates `node_modules/` and `package-lock.json` at repo root.

- [ ] **Step 3: Create `.markdownlint-cli2.jsonc`**

Create at the repo root:

```jsonc
{
  // Default rule set with two disables:
  //   MD013 (line-length) — too noisy for prose docs
  //   MD033 (inline HTML) — needed for the README's <p align="center"> logo block
  "config": {
    "default": true,
    "MD013": false,
    "MD033": false
  },
  "ignores": [
    "node_modules/**",
    "**/node_modules/**",
    "site/**",
    "**/.venv/**",
    "apps/web/playwright-report/**",
    "apps/web/test-results/**",
    "apps/web/dist/**",
    "**/__pycache__/**"
  ]
}
```

- [ ] **Step 4: Replace the `Makefile` `lint` and `fmt` targets with fan-out sub-targets**

Read the current Makefile first (`Makefile` at repo root). Replace the `.PHONY` line and the `lint` and `fmt` targets with:

```makefile
.PHONY: up up-bare down logs build test test-api test-web lint lint-api lint-web lint-md lint-actions lint-dockerfiles fmt fmt-api fmt-web docs clean

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
```

Keep the existing `up`, `up-bare`, `down`, `logs`, `build`, `test`, `test-api`, `test-web`, `docs`, `clean` targets unchanged.

- [ ] **Step 5: Verify `make lint-api` and `make lint-web` still work**

```bash
make lint-api
make lint-web
```

Expected: both pass (this is the same as the previous monolithic `lint` target's behavior).

- [ ] **Step 6: Verify `make lint-md` runs (it will report violations — that's fine, fixed in Task 5)**

```bash
make lint-md || true
```

Expected: command runs to completion. May exit non-zero with markdown violations listed. Note the violation count for the next task's reference.

- [ ] **Step 7: Verify `make lint-actions` and `make lint-dockerfiles` skip cleanly when binaries are absent**

```bash
make lint-actions
make lint-dockerfiles
```

Expected: prints "X not on PATH; skipping (CI will still run it)" and exits 0 if the binaries are not installed locally; runs the linter and reports violations otherwise.

- [ ] **Step 8: Commit**

```bash
git add package.json package-lock.json .markdownlint-cli2.jsonc Makefile
git commit -m "lint: add markdownlint at repo root + Makefile sub-targets (Task 1)"
```

---

### Task 2: Add new CI jobs (markdown, actions, dockerfile) with `continue-on-error: true`

**Files:**

- Modify: `.github/workflows/lint.yml`

- [ ] **Step 1: Edit `.github/workflows/lint.yml` to add three new jobs**

Append the following jobs to the `jobs:` block (keep the existing `api` and `web` jobs unchanged):

```yaml
  markdown:
    runs-on: ubuntu-latest
    continue-on-error: true
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: package-lock.json
      - run: npm ci
      - run: npx markdownlint-cli2 "**/*.md"

  actions:
    runs-on: ubuntu-latest
    continue-on-error: true
    steps:
      - uses: actions/checkout@v4
      - name: Run actionlint
        run: |
          docker run --rm -v "$PWD:/repo" -w /repo \
            rhysd/actionlint:latest -color

  dockerfile:
    runs-on: ubuntu-latest
    continue-on-error: true
    steps:
      - uses: actions/checkout@v4
      - name: Run hadolint
        run: |
          for f in apps/api/Dockerfile apps/api/Dockerfile.dev apps/web/Dockerfile apps/web/Dockerfile.dev; do
            echo "==> $f"
            docker run --rm -i hadolint/hadolint:latest-alpine < "$f"
          done
```

- [ ] **Step 2: Push and verify CI runs the new jobs**

```bash
git add .github/workflows/lint.yml
git commit -m "lint: add markdown/actions/dockerfile CI jobs (continue-on-error) (Task 2)"
git push
```

Expected: GitHub Actions runs all 5 jobs in `lint`. The new three may fail but don't block the workflow because `continue-on-error: true`. The `api` and `web` jobs still pass as before.

---

## Phase 2 — Fix existing violations (spec-sequenced order)

### Task 3: Fix hadolint findings in Dockerfiles

**Files:**

- Modify: `apps/api/Dockerfile`, `apps/api/Dockerfile.dev`, `apps/web/Dockerfile`, `apps/web/Dockerfile.dev`

- [ ] **Step 1: Run hadolint locally on each Dockerfile**

If `hadolint` is not on PATH, use the docker image:

```bash
for f in apps/api/Dockerfile apps/api/Dockerfile.dev apps/web/Dockerfile apps/web/Dockerfile.dev; do
  echo "==> $f"
  docker run --rm -i hadolint/hadolint:latest-alpine < "$f"
done
```

Expected output: a list of `DLNNNN`-prefixed warnings/errors per file. Common findings to expect:

- `DL3008` — pin apt versions (`apt-get install -y --no-install-recommends pkg=version`)
- `DL3009` — `apt-get clean` / `rm -rf /var/lib/apt/lists/*` after install
- `DL3015` — use `apt-get install --no-install-recommends`
- `DL3007` — pin base image to a SHA or specific tag
- `DL3059` — multiple consecutive `RUN` instructions

- [ ] **Step 2: Apply fixes**

For each finding:

- If pinning a version is appropriate, do it. If pinning would break floating-tag intent, add `# hadolint ignore=DL3008` on the `RUN` line with a brief justification comment.
- For missing `--no-install-recommends`, add it.
- For missing apt cache cleanup, append `&& rm -rf /var/lib/apt/lists/*` to the `apt-get` `RUN`.
- Common pattern to combine into a single RUN:

  ```dockerfile
  RUN apt-get update \
      && apt-get install -y --no-install-recommends pkg \
      && rm -rf /var/lib/apt/lists/*
  ```

- [ ] **Step 3: Re-run hadolint to confirm clean**

```bash
for f in apps/api/Dockerfile apps/api/Dockerfile.dev apps/web/Dockerfile apps/web/Dockerfile.dev; do
  echo "==> $f"
  docker run --rm -i hadolint/hadolint:latest-alpine < "$f"
done
```

Expected: each file prints `==> path` with no follow-up lines (clean).

- [ ] **Step 4: Verify Docker images still build**

```bash
make build
```

Expected: docker compose builds successfully — pins haven't broken anything.

- [ ] **Step 5: Commit**

```bash
git add apps/api/Dockerfile apps/api/Dockerfile.dev apps/web/Dockerfile apps/web/Dockerfile.dev
git commit -m "lint: fix hadolint findings in Dockerfiles (Task 3)"
git push
```

---

### Task 4: Fix actionlint findings in workflows

**Files:**

- Modify: `.github/workflows/*.yml` (any with findings)

- [ ] **Step 1: Run actionlint locally**

```bash
docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:latest -color
```

Expected output: zero or a small number of findings. Common things actionlint catches:

- Outdated action versions
- Typos in `${{ }}` expressions
- Invalid `runs-on` labels
- Shell script issues inside `run:` blocks (delegated to shellcheck, which actionlint runs internally)

- [ ] **Step 2: Apply fixes**

Fix each finding inline. If a finding is intentional, add an `# actionlint disable` comment with a justification.

- [ ] **Step 3: Re-run actionlint to confirm clean**

```bash
docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:latest -color
```

Expected: no output, exit 0.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/
git commit -m "lint: fix actionlint findings in workflows (Task 4)"
git push
```

---

### Task 5: Fix markdownlint violations

**Files:**

- Modify: any `**/*.md` files (excluding ignored paths) with violations

- [ ] **Step 1: Run markdownlint with auto-fix**

```bash
npx markdownlint-cli2 --fix "**/*.md"
```

Expected: auto-fixable issues (trailing whitespace, blank-line-around rules, list-style consistency) are repaired in place.

- [ ] **Step 2: Run markdownlint without `--fix` to see remaining issues**

```bash
npx markdownlint-cli2 "**/*.md"
```

Expected: remaining issues are typically those requiring human judgement (heading-level skips, link refs).

- [ ] **Step 3: Apply manual fixes**

Common manual fixes:

- `MD001` — heading levels can only increment by one. Re-level headings.
- `MD025` — single `# H1` per document. If a doc has two, demote the second.
- `MD034` — bare URL → wrap in `<>` or convert to `[text](url)`.
- `MD041` — first line should be top-level heading.

- [ ] **Step 4: Re-run markdownlint to confirm clean**

```bash
npx markdownlint-cli2 "**/*.md"
```

Expected: exit 0, no output (or just the summary line).

- [ ] **Step 5: Commit**

```bash
git add -A '*.md'
git commit -m "lint: fix markdownlint violations across docs and READMEs (Task 5)"
git push
```

---

### Task 6: Align pytest-prism's ruff config with apps/api's

**Files:**

- Modify: `clients/python-pytest/pyproject.toml`
- Possibly: `clients/python-pytest/src/**/*.py`, `clients/python-pytest/tests/**/*.py` (only if `S` rules surface findings)

- [ ] **Step 1: Edit `clients/python-pytest/pyproject.toml`'s `[tool.ruff.lint]` block**

Locate the block:

```toml
[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "C4", "SIM", "RUF"]
```

Replace with:

```toml
[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "ASYNC", "S", "C4", "SIM", "RUF"]
ignore = [
  "S101",  # asserts ok in tests
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*" = ["S105", "S106", "S107"]
```

Rationale: matches `apps/api/pyproject.toml`'s rule set (api also ignores `B008` for FastAPI's `Depends()` pattern, but pytest-prism doesn't use FastAPI — keep ignore list minimal).

- [ ] **Step 2: Run ruff against pytest-prism to surface any findings**

```bash
cd clients/python-pytest && uv run ruff check .
```

Expected: clean exit, or a small number of `S` findings to address. The plugin is small (no shell-out, no `pickle`, no `yaml.load`) so 0 findings is the most likely outcome.

- [ ] **Step 3: Fix any findings inline**

If `ruff check` reports issues:

- `S603`/`S607` (subprocess) — verify the call is safe; add `# noqa: S603` with a comment explaining why if it is (e.g., args fully controlled, no shell injection vector).
- Anything else — fix the underlying code.

If 0 findings, skip to step 5.

- [ ] **Step 4: Re-run ruff to confirm clean**

```bash
cd clients/python-pytest && uv run ruff check .
```

Expected: exit 0, no findings.

- [ ] **Step 5: Verify pytest-prism's own tests still pass**

```bash
cd clients/python-pytest && uv run pytest -q --ignore=tests/contract
```

Expected: same pass count as before.

- [ ] **Step 6: Commit**

```bash
git add clients/python-pytest/pyproject.toml
# Plus any source files modified to satisfy S rules:
git add clients/python-pytest/src clients/python-pytest/tests 2>/dev/null || true
git commit -m "pytest-prism: align ruff rules with prism-api (add ASYNC, S) (Task 6)"
git push
```

Expected: CI's `pytest-prism` workflow runs ruff with the new config and stays green.

---

### Task 7: Apply ruff format pass to apps/api and add format-check to api CI

**Files:**

- Modify: any `apps/api/**/*.py` with format drift; `.github/workflows/lint.yml`

- [ ] **Step 1: Run ruff format check (no-fix) to see if there's drift**

```bash
cd apps/api && uv run ruff format --check .
```

Expected: either "X files already formatted" (clean — skip to step 4) or a list of files with drift.

- [ ] **Step 2: If drift found, apply formatting**

```bash
cd apps/api && uv run ruff format .
```

Expected: lists the files reformatted.

- [ ] **Step 3: Verify tests still pass after formatting**

```bash
cd apps/api && uv run pytest
```

Expected: same pass count as before (formatting changes are whitespace-only).

- [ ] **Step 4: If drift was found, commit the format pass first**

```bash
git add apps/api/
git commit -m "prism-api: ruff format pass (Task 7)"
```

If there was no drift, skip this commit and proceed to step 5.

- [ ] **Step 5: Edit the `api` job in `.github/workflows/lint.yml`**

Find the `api` job's `run:` block:

```yaml
      - working-directory: apps/api
        run: |
          uv pip install --system .[dev] || uv sync
          uv run ruff check .
          uv run mypy src
```

Replace with:

```yaml
      - working-directory: apps/api
        run: |
          uv pip install --system .[dev] || uv sync
          uv run ruff check .
          uv run ruff format --check .
          uv run mypy src
```

- [ ] **Step 6: Commit and push**

```bash
git add .github/workflows/lint.yml
git commit -m "prism-api: add ruff format-check to CI (Task 7)"
git push
```

Expected: api CI job runs the new format check and stays green.

---

### Task 8: Lint and type-check `scripts/` from the api job

**Files:**

- Modify: `.github/workflows/lint.yml`, possibly `scripts/*.py`

- [ ] **Step 1: Run ruff check against scripts/ via api's pyproject**

```bash
cd apps/api && uv run ruff check ../../scripts
```

Expected output: zero or a small number of findings. The scripts are stdlib-only and reasonably well-formed; `S` findings (subprocess use, etc.) are unlikely.

- [ ] **Step 2: Run ruff format check against scripts/**

```bash
cd apps/api && uv run ruff format --check ../../scripts
```

Expected output: either clean or a small drift list.

- [ ] **Step 3: Run mypy strict against scripts/**

```bash
cd apps/api && uv run mypy ../../scripts
```

Expected output: this is the first time these files are type-checked, so expect a non-trivial number of findings, especially in `upload_run.py` and `seed_demo.py`. Likely categories:

- Missing return-type annotations on functions
- Untyped `argparse.Namespace` usage (often resolved with `argparse.Namespace` as a type or with `cast`)
- `urllib`-related calls returning `Any`

`_prism_client.py` is also vendored into `pyadi-iio/test/plugins/prism_report/` — keeping it strict-typed prevents downstream churn there. If you're tempted to add `# type: ignore` to keep this task small, prefer adding the right annotation instead.

- [ ] **Step 4: Apply fixes**

For ruff findings, fix or add justified `# noqa` comments.
For format drift, run `cd apps/api && uv run ruff format ../../scripts`.
For mypy findings, add type annotations. Avoid `Any` unless genuinely the right type.

- [ ] **Step 5: Verify all three checks pass cleanly**

```bash
cd apps/api && uv run ruff check ../../scripts \
            && uv run ruff format --check ../../scripts \
            && uv run mypy ../../scripts
```

Expected: exit 0.

- [ ] **Step 6: Verify scripts still run (smoke test)**

The scripts are stdlib-only and meant to run without `pip install`. Smoke-test that the imports still work and `--help` is intact:

```bash
python3 scripts/upload_run.py --help
python3 scripts/seed_demo.py --help
```

Expected: each prints its argparse help text and exits 0.

- [ ] **Step 7: Add scripts/ commands to api's CI job**

Edit `.github/workflows/lint.yml`'s `api` job's `run:` block. After the existing commands, append:

```yaml
          uv run ruff check ../../scripts
          uv run ruff format --check ../../scripts
          uv run mypy ../../scripts
```

So the full `run:` block reads:

```yaml
      - working-directory: apps/api
        run: |
          uv pip install --system .[dev] || uv sync
          uv run ruff check .
          uv run ruff format --check .
          uv run mypy src
          uv run ruff check ../../scripts
          uv run ruff format --check ../../scripts
          uv run mypy ../../scripts
```

- [ ] **Step 8: Commit and push**

```bash
git add scripts/ .github/workflows/lint.yml
git commit -m "prism-api: lint and mypy scripts/ via api's pyproject (Task 8)"
git push
```

Expected: api CI job stays green.

---

### Task 9: Install jsx-a11y plugin and fix violations

**Files:**

- Modify: `apps/web/package.json`, `apps/web/package-lock.json`, `apps/web/eslint.config.js`, `apps/web/src/**/*.{ts,tsx}`

- [ ] **Step 1: Install eslint-plugin-jsx-a11y**

```bash
cd apps/web && npm install -D eslint-plugin-jsx-a11y
```

Expected: package added to `devDependencies`, lockfile updated.

- [ ] **Step 2: Edit `apps/web/eslint.config.js` to wire the plugin**

Current relevant section:

```js
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
```

Add the import:

```js
import jsxA11y from 'eslint-plugin-jsx-a11y';
```

In the `{ files: ['**/*.{ts,tsx}'], ... }` config block, update `plugins` and `rules`:

```js
    plugins: {
      '@typescript-eslint': tsPlugin,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      'jsx-a11y': jsxA11y,
    },
    rules: {
      ...tsPlugin.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      ...jsxA11y.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      'no-undef': 'off',
    },
```

- [ ] **Step 3: Run lint to surface violations**

```bash
cd apps/web && npm run lint
```

Expected: a list of `jsx-a11y/...` violations. Common categories given a Chakra UI v3 app:

- `jsx-a11y/alt-text` — `<img>` without `alt`
- `jsx-a11y/click-events-have-key-events` — clickable non-button elements
- `jsx-a11y/no-static-element-interactions` — same family
- `jsx-a11y/anchor-is-valid` — `<a>` without proper `href`
- `jsx-a11y/label-has-associated-control` — `<label>` without `htmlFor` or wrapping

Estimate: 5–15 violations across `apps/web/src/components/`, `apps/web/src/pages/`.

- [ ] **Step 4: Fix violations**

Apply fixes per category:

- Missing `alt`: add descriptive `alt` for content images, `alt=""` for decorative ones.
- Click on `<div>`/`<span>`: switch to `<button type="button">` (Chakra `<Button>` is preferred where context allows).
- `<a>` with `onClick` and no real navigation: switch to `<button>` or add proper `href`.
- `<label>` without `htmlFor`: add it, or wrap the input element directly.

For genuine false positives, disable the specific rule on the specific line with `// eslint-disable-next-line jsx-a11y/<rule>` and a brief justification comment.

- [ ] **Step 5: Verify lint passes**

```bash
cd apps/web && npm run lint
```

Expected: exit 0, no warnings (since `--max-warnings 0` is in the script).

- [ ] **Step 6: Verify tests and build still pass**

```bash
cd apps/web && npm test && npm run build
```

Expected: tests pass, build succeeds. Component changes (e.g., `<div>` → `<button>`) shouldn't break tests, but verify.

- [ ] **Step 7: Commit and push**

```bash
git add apps/web/package.json apps/web/package-lock.json apps/web/eslint.config.js apps/web/src/
git commit -m "prism-web: enable jsx-a11y eslint rules and fix violations (Task 9)"
git push
```

Expected: web CI job passes.

---

### Task 10: Install simple-import-sort and bulk-sort imports

**Files:**

- Modify: `apps/web/package.json`, `apps/web/package-lock.json`, `apps/web/eslint.config.js`, every `.ts` and `.tsx` file under `apps/web/src/`, `apps/web/tests/`, and `apps/web/e2e/`

- [ ] **Step 1: Install eslint-plugin-simple-import-sort**

```bash
cd apps/web && npm install -D eslint-plugin-simple-import-sort
```

- [ ] **Step 2: Edit `apps/web/eslint.config.js` to wire the plugin and rules**

Add the import at the top:

```js
import simpleImportSort from 'eslint-plugin-simple-import-sort';
```

In the `{ files: ['**/*.{ts,tsx}'], ... }` config block, update `plugins` and `rules` to add the plugin and two rules:

```js
    plugins: {
      '@typescript-eslint': tsPlugin,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      'jsx-a11y': jsxA11y,
      'simple-import-sort': simpleImportSort,
    },
    rules: {
      ...tsPlugin.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      ...jsxA11y.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      'no-undef': 'off',
      'simple-import-sort/imports': 'error',
      'simple-import-sort/exports': 'error',
    },
```

- [ ] **Step 3: Commit the rule additions (lint will be failing at this point — that's intentional, fixed in step 4)**

```bash
git add apps/web/package.json apps/web/package-lock.json apps/web/eslint.config.js
git commit -m "prism-web: enable simple-import-sort eslint rules (Task 10)"
```

**Do not push yet** — pushing now would break web CI. The next step lands the bulk fix in a separate commit per the spec ("committed as a distinct commit from the rule additions for review clarity").

- [ ] **Step 4: Run eslint --fix to bulk-sort imports across the project**

```bash
cd apps/web && npx eslint . --fix
```

Expected: every `.ts`/`.tsx` file with multi-import blocks gets reordered. Exit code may still be non-zero if there are non-fixable issues; review the remaining list and address case-by-case.

- [ ] **Step 5: Verify lint, build, and tests all pass**

```bash
cd apps/web && npm run lint && npm run build && npm test
```

Expected: all three exit 0. Sort changes are syntactically inert; tests should not regress.

- [ ] **Step 6: Commit the bulk fix and push**

```bash
git add apps/web/src apps/web/tests apps/web/e2e
git commit -m "prism-web: bulk-sort imports via simple-import-sort --fix (Task 10)"
git push
```

Expected: web CI job stays green now that both commits are landed together.

---

## Phase 3 — Gating

### Task 11: Flip new CI jobs from `continue-on-error: true` to gating

**Files:**

- Modify: `.github/workflows/lint.yml`

- [ ] **Step 1: Verify all five lint workflow jobs are currently green**

Visit the GitHub Actions UI for the most recent push and confirm `api`, `web`, `markdown`, `actions`, `dockerfile` all show green checks. If any are red, return to the corresponding fix task above and resolve before proceeding.

- [ ] **Step 2: Edit `.github/workflows/lint.yml` to remove `continue-on-error: true`**

For each of the `markdown`, `actions`, and `dockerfile` jobs, delete the `continue-on-error: true` line.

- [ ] **Step 3: Run the full `make lint` locally (final smoke test)**

```bash
make lint
```

Expected: exits 0, all five sub-targets pass. (`lint-actions` and `lint-dockerfiles` may print "skipping" notices if those binaries aren't installed locally — that's fine, CI is the source of truth for those.)

- [ ] **Step 4: Commit and push**

```bash
git add .github/workflows/lint.yml
git commit -m "lint: gate markdown/actions/dockerfile CI jobs (remove continue-on-error) (Task 11)"
git push
```

Expected: all five lint jobs run and gate. From this commit onward, any future violation in any of these tools will block merges.

---

## Verification checklist (run after Task 11)

- [ ] `make lint` exits 0 locally (with all binaries available, or with skip notices for actionlint/hadolint).
- [ ] All five jobs in the GitHub Actions `lint` workflow run and pass without `continue-on-error`.
- [ ] `clients/python-pytest/pyproject.toml`'s `[tool.ruff.lint] select` matches `apps/api/pyproject.toml`'s.
- [ ] `apps/web/eslint.config.js` references `jsx-a11y` and `simple-import-sort` plugins.
- [ ] `cd apps/api && uv run mypy ../../scripts` exits 0.
- [ ] `npm run build` and `npm test` in `apps/web` exit 0.
- [ ] `make test-api` and `make test-web` exit 0 (no test regressions from format/sort/a11y changes).
- [ ] CI's existing branch-protection / required-checks settings include the new gating jobs (this may need a manual repo-settings update by the maintainer; flag in the PR description).

## Rollback strategy

If anything goes sideways, each task is its own commit; revert the offending commit(s) and push. The new tooling (`package.json`, `.markdownlint-cli2.jsonc`, new CI jobs) is additive and can be removed cleanly.
