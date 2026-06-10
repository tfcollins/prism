# Matrix Dashboard — Design Spec

**Date:** 2026-06-09
**Status:** Approved for planning
**Author:** Travis F. Collins (with Claude Code)

## Summary

A glanceable **status wall** that shows the latest pass/fail status of supported
boards/platforms (the Kuiper Linux project matrix) as a 2D coverage grid. Rows are
ADI hardware, columns are carrier/dev platforms, and each cell shows the latest test
run's status. The view is designed to be opened on a large TV across the lab and
understood at a glance, and can be filtered by the boot-image file used to test the
system.

The dashboard is available per Prism project (showing that project's subset of
boards) and as a global **superset** that unions every run tagged
`kuiper-linux-release` across all projects. Users enable the dashboard via a new
per-user settings store; matrix configuration (curated extras, tag keys, thresholds)
is shared/admin-managed.

## Goals

- A 2D coverage matrix (rows = `hw`, cols = `platform`) that reads clearly from
  across a room on a large monitor.
- Latest-run status per `hw × platform` cell, with visual treatment for **stale**
  results and **no-run** (gap) intersections.
- Filter the whole wall by `boot_file` (single or multiple values).
- Per-project view **and** a global superset view across the `kuiper-linux-release`
  tag.
- Per-user enablement and lightweight per-user preferences.
- A dedicated fullscreen kiosk route with auto-refresh and optional filter rotation
  so one TV needs no interaction.

## Non-goals

- No live push (SSE/WebSocket) in v1 — polling only.
- No materialized/cached matrix table in v1 — computed on the fly.
- No project-level tagging infrastructure — the superset is driven by the existing
  run-level `RunTag`.
- No changes to ingest, the worker, or the `TestRun`/`RunTag` schema.
- Not scraping the Kuiper wiki to build the grid.

## Decisions (resolved during brainstorming)

| Topic | Decision |
| --- | --- |
| Layout | Bold 2D coverage matrix (rows = `hw`, cols = `platform`), gradient cells, glow on fail, corner badge on stale, dashed "no run". |
| Cell grid source | Derived from observed tag values **plus** optional curated pinned rows/cols. |
| Run → cell mapping | Existing `RunTag` key/value pairs: `hw` (row), `platform` (column), `boot_file` (filter). |
| Cell status | Status of the single latest completed run for that `hw × platform` within the active filter/scope. |
| Staleness | Configurable threshold (`stale_after_hours`, default **48**); computed server-side. |
| Boot-file filter | Top filter bar, single or multiple `boot_file` values. |
| Data scope | Per-project (`project:<slug>`) and global superset (`global`) across runs tagged `kuiper-linux-release`. |
| Settings scope | Per-user enable + prefs (new generic `user_settings` table); shared/admin `matrix_config`. |
| Backend compute | On-the-fly aggregation over existing tables (no cache table). |
| Kiosk | Dedicated fullscreen route `/kiosk/matrix` (no app chrome). |
| Refresh | Poll ~30s (configurable) + optional client-side rotation through saved boot-file filters. |

## Architecture

The feature slots into Prism's existing router → repo → model layering. No new
services, no SSE, no cache tables, no worker changes.

```text
Browser (TV kiosk or normal page)
  │  GET /api/v1/matrix?scope=...&boot_file=...      ← poll every ~refresh_seconds
  ▼
routers/matrix.py ──► repos/matrix.py ──► RunTag + TestRun (existing tables)
  │                          └─ groups by (hw, platform), latest per cell
  ▼
routers/user_settings.py ──► repos/user_settings.py ──► user_settings (NEW table)
routers/matrix.py (config) ──► matrix_config (NEW table: per-project + global)
```

### New backend modules (`apps/api/src/prism_api/`)

- `models/user_settings.py` — generic per-user key/JSON store.
- `models/matrix_config.py` — shared/admin matrix configuration per scope.
- `repos/user_settings.py` — read/upsert per-user settings.
- `repos/matrix.py` — the matrix computation (latest-per-cell aggregation).
- `routers/user_settings.py` — `me/settings` endpoints.
- `routers/matrix.py` — matrix read endpoint + admin config endpoints.
- `schemas/matrix.py` — pydantic request/response models.
- `migrations/versions/*` — two Alembic migrations (one per new table).

### New frontend modules (`apps/web/src/`)

- `pages/MatrixDashboardPage.tsx` — normal page with Prism chrome.
- `pages/MatrixKioskPage.tsx` — fullscreen kiosk page (no `AppShell`).
- `components/MatrixGrid.tsx` — shared grid renderer (the bold style).
- Settings UI to enable the dashboard + set per-user prefs.
- Admin config form (minimal) under the existing `/admin` page.
- react-query hooks in `api/` (`useMatrix`, `useUserSetting`, `useUpsertUserSetting`,
  `useMatrixConfig`, `useUpsertMatrixConfig`).

## Data model

### `user_settings` (new — generic, reusable beyond this feature)

| Column | Type | Notes |
| --- | --- | --- |
| `user_id` | FK → users.id | part of composite PK |
| `key` | string | part of composite PK |
| `value` | JSON | arbitrary blob |

Composite primary key `(user_id, key)`. This feature uses key `matrix_dashboard`:

```jsonc
{
  "enabled": true,
  "default_scope": "project:kuiper-linux",   // or "global"
  "boot_file_filter": ["zynqmp-common"],
  "rotate": true
}
```

### `matrix_config` (new — shared/admin config)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | PK | |
| `scope` | string, unique | `project:<slug>` or the literal `global` |
| `config` | JSON | see below |

```jsonc
{
  "row_key": "hw",
  "col_key": "platform",
  "filter_key": "boot_file",
  "curated_rows": [],            // pinned rows to show even with zero runs
  "curated_cols": [],            // pinned columns to show even with zero runs
  "stale_after_hours": 48,
  "refresh_seconds": 30,
  "rotate_filters": []           // ordered boot_file values for kiosk rotation
}
```

Tag-key names (`row_key`/`col_key`/`filter_key`) default to `hw`/`platform`/`boot_file`
and are stored in config (not surfaced in the UI) so a future team can override them.
If no `matrix_config` row exists for a scope, defaults are applied — the feature works
before any admin setup.

### No changes to `TestRun` / `RunTag`

Cells are computed entirely from existing tags. The global superset is defined as
**any run carrying the tag key `kuiper-linux-release`** (its value, e.g. `2024_R2`,
is reserved for a future release selector and is not used to filter in v1).

## API

### Matrix read (hot path, polled)

```text
GET /api/v1/matrix?scope=<project:slug|global>&boot_file=<v>&boot_file=<v2>
```

Response:

```jsonc
{
  "scope": "project:kuiper-linux",
  "generated_at": "2026-06-09T12:00:00Z",
  "row_key": "hw",
  "col_key": "platform",
  "rows": ["ad9081", "adrv9009"],            // observed ∪ curated_rows, sorted
  "cols": ["zcu102", "zc706"],               // observed ∪ curated_cols, sorted
  "boot_files": ["zynqmp-common", "zynq-common"],   // available filter values
  "stale_after_hours": 48,
  "summary": { "pass": 14, "fail": 2, "mixed": 1, "error": 0, "no_run": 7 },
  "unplaced_runs": 0,                         // runs missing hw or platform
  "cells": {
    "ad9081|zcu102": {
      "status": "fail",
      "run_id": "…",
      "passed": 403,
      "total": 412,
      "finished_at": "…",
      "age_seconds": 3600,
      "stale": false
    }
    // a missing key ⇒ "no run" cell
  }
}
```

Cell keys are `"{row_value}|{col_value}"`. Status values reuse the existing
`RunStatus` enum (`pass`/`fail`/`mixed`/`error`/`pending`); `pending` runs are
ignored when selecting the latest completed run.

### Per-user settings (generic pair)

```text
GET  /api/v1/me/settings/{key}      → value JSON (404 ⇒ client uses defaults)
PUT  /api/v1/me/settings/{key}      → upsert value JSON (CSRF-protected)
```

### Admin matrix config

```text
GET  /api/v1/matrix/config?scope=…  → effective config (defaults merged)
PUT  /api/v1/matrix/config?scope=…  → admin-only, CSRF-protected
```

## Cell computation (`repos/matrix.py`)

All work happens in SQL against existing tables:

1. **Select candidate runs** for the scope:
   - `project:<slug>` → runs in that project.
   - `global` → runs whose `run_id` appears in `RunTag` with
     `key="kuiper-linux-release"`.
2. **Apply the boot-file filter** (if any): join `RunTag key=filter_key`,
   `value IN (...)`.
3. **Join axis tags**: resolve each run's `row_key` value and `col_key` value.
   Runs missing either are excluded and counted toward `unplaced_runs`.
4. **Latest per cell**: partition by `(row_value, col_value)`, order by
   `finished_at` desc with fallback to `created_at`, take the first. Use
   `DISTINCT ON` on Postgres and an equivalent window-function path for the SQLite
   test DB. Ignore `pending` runs when choosing the latest completed run.
5. **Build the grid**: `rows = sorted(observed_row_values ∪ curated_rows)`,
   `cols = sorted(observed_col_values ∪ curated_cols)`. Emit a cell per latest run;
   intersections with no run are simply absent in `cells` → rendered as "no run".
6. **Staleness**: `stale = age_seconds > stale_after_hours * 3600`, computed
   server-side so every client agrees.
7. **Summary**: tally statuses across the full grid (`rows × cols`), counting
   empty intersections as `no_run`.

Deterministic tiebreak when timestamps are equal: order by `finished_at`, then
`created_at`, then `id`.

## Frontend

### Routes

- `/matrix` and `/projects/:slug/matrix` → `MatrixDashboardPage` (normal Prism
  chrome, scope selector, filter bar, settings affordance).
- `/kiosk/matrix` → `MatrixKioskPage` (no `AppShell`/nav, edge-to-edge, dark,
  TV-oriented). Reads `scope` and `boot_file` from query params so a TV bookmark is
  self-contained.

Both render the shared `MatrixGrid`.

### `MatrixGrid` (bold style, approved mockup)

Gradient status cells with icon + status word + `passed/total` counts + last-run age;
failing cells glow; stale cells get a corner badge; no-run intersections are
dashed/dim. A KPI summary bar (pass/fail/mixed counts) and a legend sit above the
grid. Row headers show the eval-board sub-label; column headers show the boot-image
family sub-label.

### Data + liveness

- react-query `useMatrix(scope, bootFiles)` with `refetchInterval` from config
  (~`refresh_seconds`).
- A subtle "updated Ns ago" derived from `generated_at` shows liveness.
- **On fetch error, keep the last good data** and show an unobtrusive
  "reconnecting…" chip — never blank the wall.

### Filter rotation (kiosk)

When `rotate` is enabled, a client timer cycles through `rotate_filters` from config
every N seconds, updating the active `boot_file` filter and showing a small
"showing: <boot_file>" caption. On the normal page, rotation pauses on user
interaction; in kiosk it is always on.

### Enabling the dashboard

A per-user toggle (in a Settings/profile area) writes
`me/settings/matrix_dashboard`. When enabled, the **Matrix** nav entry appears for
that user; when disabled, it is hidden. Per-user prefs (default scope, default
boot-file filter, rotate on/off) live in the same blob and seed the page on load.

### Admin config UI

A minimal form under the existing `/admin` page edits a scope's `matrix_config`:
curated extra rows/cols, `stale_after_hours`, `refresh_seconds`, `rotate_filters`,
and (optionally) the tag-key overrides. Shipping with defaults means this is editable
but not required for the feature to function.

## Error handling & edge cases

- **Runs missing `hw` or `platform`** → excluded from the grid, surfaced via
  `unplaced_runs` and a UI footnote so they are not silently lost.
- **No matching runs** → render the curated grid (if any) all-"no run", else a
  friendly empty state. Never a blank TV.
- **Equal timestamps** → deterministic tiebreak (`finished_at`, `created_at`, `id`).
- **Mixed boot-file selection** → "latest per cell" is computed within the union of
  selected boot-files.
- **Unknown/`pending` status** → treated as no completed result for that cell.
- **Settings 404 / config absent** → defaults applied; feature works before any
  setup.
- **Kiosk auth** → the kiosk route is still behind Prism auth; a wall display needs a
  logged-in session (documented in the how-to).

## Testing

### Backend (`pytest`, SQLite + moto)

- Latest-per-cell selection picks the most recent completed run.
- Staleness boundary (just under / just over `stale_after_hours`).
- Boot-file filter (single and multiple values).
- Global superset via the `kuiper-linux-release` tag.
- Curated extras union into rows/cols.
- `unplaced_runs` counting for runs missing `hw`/`platform`.
- Summary tallies including `no_run`.
- Settings + config upsert and permissions (config is admin-only; CSRF enforced).

### Frontend (`vitest`)

- `MatrixGrid` renders each status / stale / no-run state.
- KPI summary correctness.
- Filter bar single + multi select.
- Rotation timer behavior.
- "Keep last good data" on fetch error.

### E2E (`playwright`, seeded demo)

- Enable via settings → Matrix nav appears → grid renders.
- Kiosk route hides app chrome.
- axe a11y clean — verify status colors meet contrast in both light and dark themes
  (the bold palette must pass).

### Seed data

Extend `scripts/seed_demo.py` to emit runs tagged `hw` / `platform` / `boot_file`
(and some `kuiper-linux-release`) so the dashboard has realistic data in dev and e2e.

## Open questions / future work

- Release selector driven by the `kuiper-linux-release` tag value (e.g. `2024_R2`).
- Optional materialized matrix cache if dataset growth ever makes on-the-fly
  aggregation too slow.
- Live push (SSE/WebSocket) if 30s polling proves too coarse.
- Drill-down from a cell into per-`boot_file` breakdown or the underlying runs.
