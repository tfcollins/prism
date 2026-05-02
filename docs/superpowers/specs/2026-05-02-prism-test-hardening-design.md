# Test Hardening — Design

**Status:** Approved
**Date:** 2026-05-02
**Scope:** `prism/` only

## Context

After the lint-hardening lane (PR #3, merged), the repo's lint posture is uniform across deliverables and CI-gated. The next stabilization lane targets testing infrastructure. This lane is intentionally narrow: **measure, don't write more tests.** Filling in component or e2e coverage gaps is a separate brainstorm that depends on what coverage measurement reveals.

Today's testing surface:

| Surface | Tests | Tooling |
|---|---|---|
| `apps/api` | 103 across 33 files | pytest 8 + pytest-asyncio + moto[s3] + freezegun + httpx |
| `clients/python-pytest` | 38 unit + a contract suite excluded from CI | pytest |
| `apps/web` (component/unit) | 18 across 4 files | vitest + jsdom + Testing Library |
| `apps/web` (e2e) | 2 specs (login, compare) | Playwright |
| Cross-cutting | none | no coverage anywhere; no runtime a11y; no flake-retry |

This spec defines a single coordinated PR that adds three pieces of testing infrastructure without committing to an open-ended write-tests effort.

## Goal

Three improvements, scope-bounded, in one PR:

- **Coverage measurement** for api, pytest-prism, and web — reported in CI logs as a terminal summary plus uploaded as an HTML artifact. **No thresholds.** Goal: know where we are.
- **Runtime a11y** via `@axe-core/playwright` in existing e2e specs, gating on `serious`/`critical` violations. Closes the gap jsx-a11y can't see (Chakra `<Box onClick>` patterns).
- **Test ergonomics** — pytest parallel execution, slow-test reporting, Playwright retry-on-flake, plus `pytest-randomly` and `pytest-clarity` for assertion-quality.

## Out of scope (other lanes / future work)

- **Frontend component tests for currently-untested components.** 30+ untested `.ts`/`.tsx` files; would be unbounded. Belongs in a separate brainstorm informed by what coverage measurement reveals.
- **More e2e flows.** ProjectsPage, ProjectDashboardPage, RunDetailPage have no e2e specs. Same reason.
- **Coverage thresholds.** Deferred until we've measured and decided what floors are appropriate.
- **Codecov / SaaS coverage trending.** Declined for this lane; CI artifact + log summary is the chosen reporting mechanism.
- **Playwright code coverage.** Instrumenting browser code through Vite for e2e adds complexity without payoff; vitest's component/integration coverage exercises the same source paths.
- **Contract tests in `clients/python-pytest/tests/contract/`.** Currently excluded from CI; a separate decision about whether to wire any of them in.

## Architecture

### Orchestration

No new orchestrator. Three changes stay in their existing homes.

- **Coverage** runs inside the existing test workflows: `test-backend.yml`, `pytest-prism.yml`, `test-frontend.yml`. Each invokes its test runner with coverage flags (already wired through `pyproject.toml addopts` for pytest; `vitest run --coverage` for web). Terminal summary prints to the workflow log; HTML report uploads as a workflow artifact.
- **Runtime a11y** runs inside the existing `playwright` job in `e2e.yml`. A new helper (`apps/web/e2e/helpers/axe.ts`) exports `expectNoSeriousAxeViolations(page)`. Each existing spec calls it at logical settling points. No new CI job.
- **Ergonomics** are pure config additions to `pyproject.toml` (per Python deliverable) and `playwright.config.ts`. No code changes.

### Coverage tool selection

- **Python:** `pytest-cov` (de facto standard; adds `--cov-report=term-missing` for the log summary and `--cov-report=html:htmlcov` for the artifact).
- **Web:** `@vitest/coverage-v8` (built into vitest's coverage interface; no instrumentation overhead since v8 emits coverage natively).
- **Playwright/e2e:** *no coverage*. Browser-code instrumentation through Vite during e2e is complex; vitest's component/integration coverage already exercises the same source.

### Runtime a11y gating model

`expect.soft(violations).toEqual([])` initially. Soft assertions report-but-don't-fail per Playwright semantics — violations show in the HTML report and stdout, but the test still passes. After existing violations are fixed (Phase 2 of rollout), the helper switches to hard `expect(...)` so future a11y regressions block CI.

This is the same rollout shape as the lint lane's `continue-on-error: true` pattern.

## Per-lane changes

### Lane A — Coverage measurement

**`apps/api/pyproject.toml`:**
- `[dependency-groups] dev` adds `pytest-cov>=5`.
- New section `[tool.coverage.run]` with `source = ["src/prism_api"]`, `branch = false`.
- New section `[tool.coverage.report]` with `show_missing = true`, `skip_covered = false`, `exclude_lines = ["pragma: no cover", "if TYPE_CHECKING:", "raise NotImplementedError"]`.
- `[tool.pytest.ini_options] addopts` gains `--cov --cov-report=term-missing --cov-report=html:htmlcov --cov-report=xml:coverage.xml` (xml for tooling friendliness; not used in this lane but cheap to emit).

**`clients/python-pytest/pyproject.toml`:**
- Same pattern; `source = ["src/pytest_prism"]`.

**`apps/web/package.json`:**
- `devDependencies` adds `@vitest/coverage-v8` (matching the vitest 2.x major already pinned).

**`apps/web/vitest.config.ts`:**
- `test.coverage` block: `{ provider: 'v8', reporter: ['text', 'html'], reportsDirectory: 'coverage', include: ['src/**/*.{ts,tsx}'], exclude: ['src/**/*.d.ts', 'src/main.tsx'] }`.
- Note: vitest's "text" reporter prints the summary to stdout; that's the log-summary equivalent of pytest's `term-missing`.

**CI workflows:**
- `test-backend.yml`'s pytest invocation already gets coverage from `addopts`. Append a final step using `actions/upload-artifact@v4` with `name: coverage-api`, `path: apps/api/htmlcov`.
- `pytest-prism.yml` analogously: `name: coverage-pytest-prism`, `path: clients/python-pytest/htmlcov`. Matrix consideration: pytest-prism runs across Python 3.10/3.11/3.12 — only upload coverage from the 3.12 job to avoid artifact name collisions (use `if: matrix.python-version == '3.12'`).
- `test-frontend.yml` (`vitest` job): pass `-- --coverage` to `npm test` (or use `npx vitest run --coverage`); upload `apps/web/coverage/` as `coverage-web`.

**`.gitignore`:**
- Add `htmlcov/`, `coverage.xml`, `coverage/`, `.coverage` under the existing Python and Node sections (some already covered; verify).

### Lane D — Runtime a11y

**`apps/web/package.json`:**
- `devDependencies` adds `@axe-core/playwright` (matches `@playwright/test` major already in deps).

**New file `apps/web/e2e/helpers/axe.ts`:**

```ts
import { expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

export async function expectNoSeriousAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  const seriousOrCritical = results.violations.filter(
    v => v.impact === 'serious' || v.impact === 'critical',
  );
  // Soft assertion: reports findings but does not fail the test.
  // Switch to hard `expect(...)` after existing violations are fixed.
  expect.soft(seriousOrCritical, formatAxeViolations(seriousOrCritical)).toEqual([]);
}

function formatAxeViolations(violations: { id: string; impact: string | null | undefined; help: string }[]): string {
  if (violations.length === 0) return 'no violations';
  return violations.map(v => `${v.impact} ${v.id}: ${v.help}`).join('\n');
}
```

**Existing specs:**
- `apps/web/e2e/login.spec.ts`: add one `await expectNoSeriousAxeViolations(page)` after login completes (page has settled into the dashboard).
- `apps/web/e2e/compare.spec.ts`: add calls at two settling points — after the run-list renders, and after the compare panel is open.

### Lane F — Test ergonomics

**`apps/api/pyproject.toml`:**
- `[dependency-groups] dev` adds `pytest-xdist>=3.6`, `pytest-randomly>=3.15`, `pytest-clarity>=1.0`.
- `[tool.pytest.ini_options] addopts` gains `-n auto --durations=10`. Combined with the coverage flags from lane A, the final `addopts` reads:
  ```
  addopts = "-n auto --durations=10 --cov --cov-report=term-missing --cov-report=html:htmlcov --cov-report=xml:coverage.xml"
  ```
- `pytest-randomly` and `pytest-clarity` self-register via entry points; no further config needed.

**`clients/python-pytest/pyproject.toml`:**
- Same dev-dep additions and `addopts`.

**`apps/web/playwright.config.ts`:**
- Add `retries: process.env.CI ? 2 : 0` at the top level (alongside existing `testDir`, `use`, etc.). Local runs continue to fail fast.

**`apps/web/vitest.config.ts`:**
- No ergonomics change beyond the coverage block from lane A. Vitest is already parallel by default.

## Rollout — fix-as-part-of-lane

### Sequencing (within the implementation plan)

1. **Scaffolding phase** — coverage + ergonomics + axe helper land. Existing tests run with all new plumbing. Each tool may surface real findings:
   - `pytest-randomly`: 0–3 likely findings (hidden order-dependence; each is a real bug to fix).
   - `pytest-xdist`: 0–2 likely findings (filesystem-state collisions; each is a real bug to fix).
   - `@axe-core/playwright` with `expect.soft`: reports violations to logs but does not fail.
   - Coverage tools: zero failures by definition (no thresholds).
2. **A11y fix phase** — implement keyboard handlers on the three Chakra `<Box onClick>` sites the lint reviewer flagged in PR #3:
   - `apps/web/src/components/TestTree.tsx:119-120` — case-group expand
   - `apps/web/src/components/TestTree.tsx:186-187` — case selection
   - `apps/web/src/pages/ComparePage.tsx:72` — case selection in compare panel
   Refactor each to a Chakra `<Button variant="ghost">` or add `role="button" tabIndex={0} onKeyDown={...}` per Chakra's official a11y guidance. Re-run e2e and confirm axe reports zero serious/critical violations.
3. **Gating phase** — flip `expect.soft` to hard `expect` in `apps/web/e2e/helpers/axe.ts`. Single one-line commit. From this commit onward, any new a11y regression blocks CI.

### Estimated cost

- Phase 1: low-touch (config + helper + run). Most likely 0–5 fixes from randomly/xdist; probably zero, this is a recently-built test suite.
- Phase 2: bounded (3 known sites; each is ~10 lines of refactor).
- Phase 3: 1 line.

Total: a few hours, single PR.

## Success criteria

- `make test-api` reports coverage in its terminal output; HTML report exists in `apps/api/htmlcov/`.
- `make test-web` (or `npm test -- --coverage`) reports coverage in its terminal output; HTML report exists in `apps/web/coverage/`.
- `cd clients/python-pytest && uv run pytest -q --ignore=tests/contract` reports coverage in its terminal output.
- All three CI test workflows upload their coverage HTML as workflow artifacts visible from the run page.
- `cd apps/web && npx playwright test` runs and the HTML report shows axe results for each spec; in CI, axe violations either pass (post-Phase-2) or surface as soft-assertion notes (Phase 1).
- `cd apps/api && uv run pytest` runs in parallel via xdist (`-n auto`) and prints `--durations=10` summary.
- `playwright.config.ts` has `retries: process.env.CI ? 2 : 0`.
- After Phase 3: any new a11y regression in `TestTree.tsx`, `ComparePage.tsx`, or any other page covered by an existing e2e spec, blocks CI.

## Risks

- **`pytest-xdist` worker isolation:** if a test relies on cwd-relative paths or process-global state (e.g., a singleton), parallel execution will fail intermittently. Mitigation: address surfaced findings in Phase 1 fix-up.
- **`pytest-randomly` masking deterministic-only test design:** some tests may rely on a specific module-load order. Each finding is a real bug; if the volume is unexpectedly high (>5), reconsider scope and possibly disable randomly until those are addressed.
- **Playwright `retries: 2` masking flake:** retries hide newly-introduced flakiness from PR review. The HTML report does show retry count, but reviewers won't see it by default. Acceptable trade-off given e2e infrastructure flake is a known industry problem; revisit if retry-rate climbs.
- **`@axe-core/playwright` rule-set evolution:** axe-core ships periodic rule updates that can surface "new" violations on a previously-clean page. Mitigation: pin `@axe-core/playwright` to a specific minor version, document the update cadence as a small recurring chore.
- **Coverage tooling adding test-run time:** pytest-cov adds ~10–20% to test runtime; vitest v8 coverage adds ~5%. Combined with `pytest-xdist` parallelism, net CI time should *decrease*. If it doesn't, investigate before merging.
