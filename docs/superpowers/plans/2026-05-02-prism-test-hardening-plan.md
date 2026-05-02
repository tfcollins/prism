# Test Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add coverage measurement (api + pytest-prism + web) reported as CI log summary plus HTML artifact, runtime a11y testing via `@axe-core/playwright` with `serious`/`critical` gating, and test ergonomics (pytest parallel + randomly + clarity + slow-test reporting + Playwright retry-on-flake).

**Architecture:** No new orchestrators or workflows. Coverage flags land in existing `addopts` (pytest) / `vitest.config.ts` and existing test workflows upload HTML reports as `actions/upload-artifact@v4` artifacts. Axe runs inline in the existing `playwright` job via a new `apps/web/e2e/helpers/axe.ts` helper, using `expect.soft(...)` initially so existing violations don't block CI; flipped to hard `expect(...)` in the final task after fixes.

**Tech Stack:** pytest-cov, pytest-xdist, pytest-randomly, pytest-clarity, @vitest/coverage-v8, @axe-core/playwright, GitHub Actions, Playwright.

**Spec:** `docs/superpowers/specs/2026-05-02-prism-test-hardening-design.md`

**Commit style:**
- `prism-api:` for `apps/api/` changes (and `test-backend.yml` edits)
- `pytest-prism:` for `clients/python-pytest/` changes (and `pytest-prism.yml` edits)
- `prism-web:` for `apps/web/` changes (and `test-frontend.yml` / `e2e.yml` edits)
- All commits append ` (Task N)` matching the task number
- No `Co-Authored-By` lines (per `no-co-author` skill)

**Branch:** all work lands on `tfcollins/test-hardening` (already created). Push once after each task.

---

## File map

**Created:**
- `apps/web/e2e/helpers/axe.ts` — `expectNoSeriousAxeViolations(page)` helper

**Modified:**
- `apps/api/pyproject.toml` — coverage config + dev deps + addopts
- `clients/python-pytest/pyproject.toml` — same
- `apps/web/package.json` + `apps/web/package-lock.json` — `@vitest/coverage-v8` and `@axe-core/playwright`
- `apps/web/vitest.config.ts` — coverage block
- `apps/web/playwright.config.ts` — `retries: process.env.CI ? 2 : 0`
- `apps/web/e2e/login.spec.ts`, `apps/web/e2e/compare.spec.ts` — axe call sites
- `apps/web/src/components/TestTree.tsx` — keyboard handlers on `<Box onClick>` (Phase 2; conditional on axe findings)
- `apps/web/src/pages/ComparePage.tsx` — same (Phase 2; conditional on axe findings)
- `.github/workflows/test-backend.yml` — coverage artifact upload
- `.github/workflows/test-frontend.yml` — `--coverage` flag and artifact upload
- `.github/workflows/pytest-prism.yml` — matrix-aware coverage artifact upload (3.12 only)
- `.gitignore` — coverage output paths

---

## Phase 1 — Scaffolding (non-breaking)

### Task 1: apps/api — coverage + ergonomics

**Files:**
- Modify: `apps/api/pyproject.toml`, `.github/workflows/test-backend.yml`, `.gitignore`

- [ ] **Step 1: Edit `apps/api/pyproject.toml`'s `[dependency-groups] dev`**

Add four new dev deps. Find the existing `dev = [...]` list and append:

```toml
  "pytest-cov>=5",
  "pytest-xdist>=3.6",
  "pytest-randomly>=3.15",
  "pytest-clarity>=1.0",
```

- [ ] **Step 2: Add coverage config sections to `apps/api/pyproject.toml`**

After `[tool.mypy]` (and its overrides) and before `[tool.pytest.ini_options]`, insert:

```toml
[tool.coverage.run]
source = ["src/prism_api"]
branch = false

[tool.coverage.report]
show_missing = true
skip_covered = false
exclude_lines = [
  "pragma: no cover",
  "if TYPE_CHECKING:",
  "raise NotImplementedError",
]
```

- [ ] **Step 3: Update `addopts` in `apps/api/pyproject.toml`**

Find `[tool.pytest.ini_options]`. The current section has `testpaths`, `asyncio_mode`, and `filterwarnings` but no `addopts`. Add:

```toml
addopts = "-n auto --durations=10 --cov --cov-report=term-missing --cov-report=html:htmlcov --cov-report=xml:coverage.xml"
```

- [ ] **Step 4: Sync the venv and run pytest to verify scaffolding**

```bash
cd apps/api && uv sync --extra dev || uv sync
cd apps/api && uv run pytest -q
```
Expected: 103 tests pass. xdist message about workers should appear at the top. A coverage summary table prints at the end. The 10 slowest tests are listed.

If `pytest-randomly` surfaces an order-dependence failure: fix the underlying test (typically a fixture that mutates module-level state, or a test that depends on insertion order in a dict). Make a separate commit for each fix with message `prism-api: fix order-dependent test in <name> (Task 1)`.

If `pytest-xdist` surfaces a parallelism failure (typically two tests writing to the same `/tmp/X` path or contending on the same in-memory bucket): fix and commit similarly with message `prism-api: isolate parallel-unsafe test in <name> (Task 1)`.

- [ ] **Step 5: Edit `.github/workflows/test-backend.yml` to upload coverage as an artifact**

Read the current file first. After the existing pytest step, add:

```yaml
      - name: Upload coverage HTML
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: coverage-api
          path: apps/api/htmlcov
```

`if: always()` ensures the artifact uploads even if a test fails — useful for diagnosing coverage gaps in failing PRs.

- [ ] **Step 6: Update `.gitignore`**

Read `.gitignore`. Under the existing Python section, ensure these are listed (some may already be present; only add missing entries):

```
htmlcov/
coverage.xml
.coverage
```

- [ ] **Step 7: Commit**

```bash
git add apps/api/pyproject.toml .github/workflows/test-backend.yml .gitignore
git commit -m "prism-api: enable coverage + pytest ergonomics (xdist, randomly, clarity, durations) (Task 1)"
git push
```
Expected: CI's `pytest` job runs, posts coverage summary in log, and uploads `coverage-api` artifact.

---

### Task 2: clients/python-pytest — coverage + ergonomics

**Files:**
- Modify: `clients/python-pytest/pyproject.toml`, `.github/workflows/pytest-prism.yml`

- [ ] **Step 1: Edit `clients/python-pytest/pyproject.toml`'s `[project.optional-dependencies] dev`**

Add four new dev deps. Find the existing `dev = [...]` list and append:

```toml
  "pytest-cov>=5",
  "pytest-xdist>=3.6",
  "pytest-randomly>=3.15",
  "pytest-clarity>=1.0",
```

- [ ] **Step 2: Add coverage config sections**

After `[tool.mypy]` and before `[tool.pytest.ini_options]`, insert:

```toml
[tool.coverage.run]
source = ["src/pytest_prism"]
branch = false

[tool.coverage.report]
show_missing = true
skip_covered = false
exclude_lines = [
  "pragma: no cover",
  "if TYPE_CHECKING:",
  "raise NotImplementedError",
]
```

- [ ] **Step 3: Update `addopts`**

The current `[tool.pytest.ini_options]` has only `testpaths` and `filterwarnings`. Add `addopts`:

```toml
addopts = "-n auto --durations=10 --cov --cov-report=term-missing --cov-report=html:htmlcov --cov-report=xml:coverage.xml"
```

- [ ] **Step 4: Sync venv and verify pytest-prism still runs**

```bash
cd clients/python-pytest && uv sync --extra dev
cd clients/python-pytest && uv run pytest -q --ignore=tests/contract
```
Expected: 38 tests pass; xdist worker info at top; coverage summary at end; 10 slowest tests listed.

Same fix pattern as Task 1 if randomly/xdist surface anything (rare for a small suite).

- [ ] **Step 5: Edit `.github/workflows/pytest-prism.yml` to add matrix-aware coverage artifact upload**

After the existing test step, add:

```yaml
      - name: Upload coverage HTML
        if: always() && matrix.python-version == '3.12'
        uses: actions/upload-artifact@v4
        with:
          name: coverage-pytest-prism
          path: clients/python-pytest/htmlcov
```

The matrix guard avoids artifact name collisions (three jobs in the matrix would otherwise all try to upload the same artifact name).

- [ ] **Step 6: Commit**

```bash
git add clients/python-pytest/pyproject.toml .github/workflows/pytest-prism.yml
git commit -m "pytest-prism: enable coverage + pytest ergonomics (Task 2)"
git push
```
Expected: pytest-prism workflow runs across 3.10/3.11/3.12; only 3.12 uploads coverage artifact.

---

### Task 3: apps/web — coverage

**Files:**
- Modify: `apps/web/package.json`, `apps/web/package-lock.json`, `apps/web/vitest.config.ts`, `.github/workflows/test-frontend.yml`, `.gitignore`

- [ ] **Step 1: Install `@vitest/coverage-v8`**

```bash
cd apps/web && npm install -D @vitest/coverage-v8
```
Expected: `package.json` and `package-lock.json` updated; the version chosen will match the vitest 2.x major already in deps.

- [ ] **Step 2: Edit `apps/web/vitest.config.ts` to add coverage block**

Read the current file first. Within the `defineConfig({ test: { ... } })` block, add a `coverage` key:

```ts
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      reportsDirectory: 'coverage',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.d.ts', 'src/main.tsx'],
    },
```

- [ ] **Step 3: Verify `npm test --coverage` works locally**

```bash
cd apps/web && npx vitest run --coverage
```
Expected: 18 tests pass; a coverage table prints at the end; `apps/web/coverage/index.html` is generated.

- [ ] **Step 4: Edit `.github/workflows/test-frontend.yml` to enable coverage and upload artifact**

Read the current file first. The `vitest` job's `npm test` step needs the `--coverage` flag. Two options depending on the current invocation:

If the step uses `npm test`, change to:
```yaml
      - run: npx vitest run --coverage
```

If the step already uses `npx vitest run`, append `--coverage`:
```yaml
      - run: npx vitest run --coverage
```

After the test step, add:

```yaml
      - name: Upload coverage HTML
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: coverage-web
          path: apps/web/coverage
```

- [ ] **Step 5: Update `.gitignore`**

Under the Node section, ensure `coverage/` is listed (likely already present). Verify with:

```bash
grep -n '^coverage' .gitignore
```
If not present, add `coverage/` to the Node section.

- [ ] **Step 6: Commit**

```bash
git add apps/web/package.json apps/web/package-lock.json apps/web/vitest.config.ts .github/workflows/test-frontend.yml .gitignore
git commit -m "prism-web: enable vitest coverage with v8 provider (Task 3)"
git push
```
Expected: vitest CI job runs with coverage; `coverage-web` artifact appears on the run page.

---

### Task 4: Playwright retry-on-flake

**Files:**
- Modify: `apps/web/playwright.config.ts`

- [ ] **Step 1: Read the current `apps/web/playwright.config.ts`**

Current contents:

```ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:8180',
    headless: true,
    screenshot: 'only-on-failure',
  },
  reporter: [['list']],
});
```

- [ ] **Step 2: Add `retries` to the `defineConfig` block**

Insert after `timeout: 30_000,`:

```ts
  retries: process.env.CI ? 2 : 0,
```

Final file:

```ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  retries: process.env.CI ? 2 : 0,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:8180',
    headless: true,
    screenshot: 'only-on-failure',
  },
  reporter: [['list']],
});
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/playwright.config.ts
git commit -m "prism-web: retry e2e tests twice on CI flake (Task 4)"
git push
```
Expected: e2e workflow continues to run; if any test happens to be flaky on this run, it will retry up to twice before failing.

---

### Task 5: axe-playwright integration (with soft assertions)

**Files:**
- Create: `apps/web/e2e/helpers/axe.ts`
- Modify: `apps/web/package.json`, `apps/web/package-lock.json`, `apps/web/e2e/login.spec.ts`, `apps/web/e2e/compare.spec.ts`

- [ ] **Step 1: Install `@axe-core/playwright`**

```bash
cd apps/web && npm install -D @axe-core/playwright
```

- [ ] **Step 2: Create `apps/web/e2e/helpers/axe.ts`**

```ts
import AxeBuilder from '@axe-core/playwright';
import { expect, type Page } from '@playwright/test';

type AxeViolation = {
  id: string;
  impact: 'minor' | 'moderate' | 'serious' | 'critical' | null | undefined;
  help: string;
  helpUrl: string;
  nodes: { target: string[] }[];
};

export async function expectNoSeriousAxeViolations(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  const filtered = (results.violations as AxeViolation[]).filter(
    (v) => v.impact === 'serious' || v.impact === 'critical',
  );
  // expect.soft reports findings without failing the test, so we can land
  // this helper before existing violations are fixed. Task 7 flips this to
  // hard `expect(...)` after fixes land.
  expect.soft(filtered, formatViolations(filtered)).toEqual([]);
}

function formatViolations(violations: AxeViolation[]): string {
  if (violations.length === 0) return 'no serious or critical axe violations';
  return violations
    .map((v) => {
      const targets = v.nodes.map((n) => n.target.join(' ')).join(', ');
      return `${v.impact} ${v.id}: ${v.help} (${v.helpUrl}) — targets: ${targets}`;
    })
    .join('\n');
}
```

- [ ] **Step 3: Add a call site to `apps/web/e2e/login.spec.ts`**

Read the current file first. After the existing assertion that confirms the user is logged in (e.g., a check that the dashboard is visible), add:

```ts
import { expectNoSeriousAxeViolations } from './helpers/axe';

// ... at the end of the existing login test, after the dashboard renders:
await expectNoSeriousAxeViolations(page);
```

- [ ] **Step 4: Add call sites to `apps/web/e2e/compare.spec.ts`**

Read the current file first. Add the same import. Add `await expectNoSeriousAxeViolations(page);` at two settling points:
1. After the run-list / runs table renders.
2. After the compare panel / overlay UI is visible (post-selection).

- [ ] **Step 5: Verify Playwright still runs (locally if possible, or push to test on CI)**

If a local Prism stack is available:
```bash
make up && cd apps/web && npx playwright test
```
Expected: tests pass (axe uses soft assertions; even with violations, tests pass). Test output and HTML report show axe findings.

If no local stack: push and check CI.

- [ ] **Step 6: Commit**

```bash
git add apps/web/package.json apps/web/package-lock.json apps/web/e2e/helpers/axe.ts apps/web/e2e/login.spec.ts apps/web/e2e/compare.spec.ts
git commit -m "prism-web: add @axe-core/playwright with soft assertions in e2e (Task 5)"
git push
```
Expected: e2e workflow runs; HTML report shows axe findings inline; tests pass even if violations exist.

---

## Phase 2 — Fix axe-surfaced a11y violations

### Task 6: Apply keyboard handlers to clickable Boxes

**Files (likely; depends on what axe surfaces):**
- Modify: `apps/web/src/components/TestTree.tsx`, `apps/web/src/pages/ComparePage.tsx`

- [ ] **Step 1: Run e2e locally and read axe findings**

```bash
make up && cd apps/web && npx playwright test --reporter=list
```

Look at the test output for axe-soft-assertion lines. They look like:
```
serious aria-required-children: ARIA role required-children
serious click-events-have-key-events: Ensure clickable elements are keyboard-accessible (...)
```

Capture the list of unique `id`s and which DOM `targets` are flagged.

- [ ] **Step 2: For each `<Box onClick=...>` flagged with `serious` impact, apply the keyboard-accessible pattern**

The expected pattern in `apps/web/src/components/TestTree.tsx` lines ~119-156 (case-group expand) and ~186+ (case row), based on the lint reviewer's analysis from PR #3:

For the case-group expand (line 118-130 area):

```tsx
      <Box
        onClick={() => setOpen((v) => !v)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setOpen((v) => !v);
          }
        }}
        role="button"
        tabIndex={0}
        aria-expanded={open}
        cursor="pointer"
        // ... existing styling props
```

For the case row (line 186+ area):

```tsx
    <Box
      onClick={() => onSelectCase(c.id)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelectCase(c.id);
        }
      }}
      role="button"
      tabIndex={0}
      aria-pressed={selectedCaseId === c.id}
      cursor="pointer"
      // ... existing styling props
```

For `apps/web/src/pages/ComparePage.tsx` — the `<Table.Row onClick>` at line ~71-81:

If axe flags it (table-row interactivity is unusual; axe may or may not flag), apply the same handler/role/tabIndex pattern. If axe does NOT flag the table row, leave it unchanged.

- [ ] **Step 3: Commit each fix as its own commit**

For each unique site fixed (typically 2-3), commit separately so the diff per fix is reviewable:

```bash
git add apps/web/src/components/TestTree.tsx
git commit -m "prism-web: keyboard-accessible case-group expand in TestTree (Task 6)"

git add apps/web/src/components/TestTree.tsx
git commit -m "prism-web: keyboard-accessible case row in TestTree (Task 6)"

# If ComparePage was flagged:
git add apps/web/src/pages/ComparePage.tsx
git commit -m "prism-web: keyboard-accessible compare table row (Task 6)"
```

Note: if you fix all sites in one editor pass, you can split into multiple commits via `git add -p`.

- [ ] **Step 4: Re-run e2e to verify zero serious/critical axe violations**

```bash
cd apps/web && npx playwright test
```
Expected: tests pass; HTML report and stdout show no axe-soft-assertion lines (or only `minor`/`moderate` lines, which the helper filters out).

- [ ] **Step 5: Verify vitest tests still pass**

```bash
cd apps/web && npm test
```
Expected: 18 tests pass. Adding `role="button"` and `tabIndex={0}` does not change DOM structure in a way that breaks Testing Library queries.

- [ ] **Step 6: Push**

```bash
git push
```
Expected: CI's e2e job runs; axe soft assertions report zero violations now.

---

## Phase 3 — Gating

### Task 7: Flip axe helper from soft to hard expect

**Files:**
- Modify: `apps/web/e2e/helpers/axe.ts`

- [ ] **Step 1: Verify zero serious/critical axe violations on the current branch**

```bash
cd apps/web && npx playwright test 2>&1 | grep -i 'axe\|serious\|critical' || echo "no axe issues detected"
```
Expected: prints "no axe issues detected" (or similar; no lines matching the violation pattern).

- [ ] **Step 2: Edit `apps/web/e2e/helpers/axe.ts` to use hard `expect`**

Find the line:

```ts
  expect.soft(filtered, formatViolations(filtered)).toEqual([]);
```

Replace with:

```ts
  expect(filtered, formatViolations(filtered)).toEqual([]);
```

Also update the comment above it to reflect the gating change:

```ts
  // From here on, any new serious/critical axe violation introduced by a PR
  // will fail the e2e job, blocking merge until fixed.
  expect(filtered, formatViolations(filtered)).toEqual([]);
```

- [ ] **Step 3: Re-run e2e to confirm tests still pass with hard expect**

```bash
cd apps/web && npx playwright test
```
Expected: tests pass.

- [ ] **Step 4: Commit and push**

```bash
git add apps/web/e2e/helpers/axe.ts
git commit -m "prism-web: gate e2e on serious/critical axe violations (Task 7)"
git push
```
Expected: CI passes; from this commit onward, any new a11y regression in pages exercised by e2e specs blocks merge.

---

## Verification checklist (run after Task 7)

- [ ] `cd apps/api && uv run pytest` runs in parallel via xdist (`-n auto` workers visible at top), prints coverage summary at end, prints `--durations=10` summary, exit 0.
- [ ] `cd clients/python-pytest && uv run pytest -q --ignore=tests/contract` — same indicators, exit 0.
- [ ] `cd apps/web && npx vitest run --coverage` prints coverage summary, exit 0.
- [ ] `apps/web/coverage/index.html`, `apps/api/htmlcov/index.html`, `clients/python-pytest/htmlcov/index.html` all exist after their respective test runs.
- [ ] `cd apps/web && npx playwright test` runs with `retries: 2` on CI; axe helper applies hard `expect`; zero serious/critical violations across both specs.
- [ ] CI artifacts visible on PR run: `coverage-api`, `coverage-web`, `coverage-pytest-prism` (latter from 3.12 job only).
- [ ] No regressions: existing test counts (api 103, pytest-prism 38, web 18) unchanged.

## Risks (recap from spec)

- pytest-xdist or pytest-randomly may surface real bugs during Task 1/2 — fix inline; usually rare for a recently-written suite.
- axe-core periodic rule updates may surface "new" violations later. The dependency is pinned to a minor version; review on bumps.
- Playwright `retries: 2` masks newly-introduced flake from PR review. The HTML report shows retry count but isn't shown by default.

## Rollback strategy

Each task is its own commit (or small group of commits in Task 6). Revert any commit independently. The infrastructure additions are additive — removing the new dev deps and config sections leaves the existing test setup untouched.
