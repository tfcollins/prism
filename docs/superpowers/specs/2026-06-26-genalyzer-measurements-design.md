# Design: genalyzer metrics as tracked measurements

Date: 2026-06-26

## Problem

The genalyzer metrics (SNR / SFDR / SINAD / THD / ENOB) are computed on demand
at view time and discarded. They are not tracked over time, not spec-gated, and
not in reports. Prism already has a full **measurements → specs (pass/fail) →
trends → regressions → CSV/PDF** pipeline fed only from JUnit/manifest at ingest.
This feature records the genalyzer metrics as `Measurement` rows so converter
performance rides that existing pipeline.

## Decisions (from brainstorming)

- **Enablement:** both a per-project default **and** a per-run override.
- **When:** computed once at ingest (worker), persisted as measurements.
- **Reuse:** specs/trends/regressions/CSV/PDF are untouched — they work by
  measurement name.

## Enablement

- New boolean column `projects.genalyzer_auto` (default `false`) — Alembic
  migration. The per-project default.
- Per-run override via a run tag named `genalyzer` with a boolean-ish value
  (`true/1/yes/on` vs `false/0/no/off`, case-insensitive).
- Effective rule at ingest:
  `enabled = parse_bool(tag "genalyzer") if the tag is present, else project.genalyzer_auto`.
  So a converter project enables it once; any run opts in/out via a CI tag.

A small helper `_genalyzer_enabled(project, tags) -> bool` encapsulates this.

## Recording at ingest

In `ingest.py`, while walking the archive (step 4), when an artifact is a
**waveform** kind (`WAVEFORM_CSV/NPY/HDF5`) **owned by a case** and `enabled` is
true, decode it with `load_waveform`, and if it has a sample rate, run
`genalyzer_markers.analyze(samples, sample_rate)` (defaults: harmonics 5,
Blackman-Harris). For each non-`None` metric, create a `Measurement` on that case:

| name | unit | source field |
|---|---|---|
| `genalyzer.snr` | `dB` | `snr` |
| `genalyzer.sfdr` | `dB` | `sfdr` |
| `genalyzer.sinad` | `dB` | `sinad` |
| `genalyzer.thd` | `dBc` | `thd` |
| `genalyzer.enob` | `bits` | `enob` |

Rules:

- Created with `spec_min=None, spec_max=None` — project specs apply by name at
  read time (existing behaviour), so users gate them via the normal spec system.
- One set per case: the **first** waveform artifact encountered for that case.
  (A case with no waveform, or `enabled` false, gets nothing.)
- **Best-effort:** the whole genalyzer step is wrapped in try/except and logged;
  it must never fail ingest (mirrors boot-log parsing). A waveform without a
  sample rate is skipped.
- `genalyzer` is lazy-imported inside `analyze()`, so only genalyzer-enabled
  ingests load `libgenalyzer`; the rest of the suite is unaffected.

Determining `enabled` needs the project default + the run's tags, both available
in the DB during ingest (run → project; run tags). Resolve once per run before
the archive loop.

## Reuse — no new downstream work

Because they are ordinary measurements named `genalyzer.*`, they flow into:

- the case measurements list and the `/cases/{id}` response,
- **CSV export** (`/projects/{slug}/export.csv`),
- **PDF reports** (run + compare),
- the **measurement trend** endpoint (`/projects/{slug}/measurements/{name}/trend`,
  e.g. `genalyzer.snr` over runs),
- **regressions**, and
- **spec pass/fail** — a project `SpecDefinition` for `genalyzer.snr` (etc.)
  applies `spec_min/max` at read time.

JUnit case pass/fail status is unchanged.

## Project setting surface

- `genalyzer_auto` added to the project read schema (`ProjectOut`).
- An admin-gated, CSRF-protected endpoint to set it — `PATCH /api/v1/projects/{slug}`
  with `{ "genalyzer_auto": bool }` (or a dedicated settings endpoint if PATCH
  doesn't exist; chosen during implementation to match the existing project
  router).
- Web: a small toggle on the project dashboard (admin only), mirroring the
  matrix-dashboard enable control, calling that endpoint and invalidating the
  project query.

## Testing

Backend:

- Ingest with `project.genalyzer_auto = true` and a waveform case → the 5
  `genalyzer.*` measurements exist on the case with correct units; metric values
  are sane (SNR present, finite). (Runs with `libgenalyzer` on the path, like the
  other genalyzer tests.)
- `genalyzer_auto = false` and no tag → no `genalyzer.*` measurements.
- Tag override: project off + run tag `genalyzer=true` → recorded; project on +
  `genalyzer=false` → not recorded. (Unit-test `_genalyzer_enabled` directly for
  the truth table; one ingest test for the end-to-end path.)
- A recorded `genalyzer.snr` appears in the measurement trend endpoint.
- Project setting endpoint round-trips `genalyzer_auto`.

Frontend:

- The project dashboard toggle renders for admins, reflects `genalyzer_auto`,
  and calls the setter on change (mocked hook).

## Error handling / edge cases

- `analyze()` raising or returning empty (degenerate/non-tone waveform) → no
  measurements, ingest unaffected.
- Multiple waveforms on one case → only the first is analyzed (avoids duplicate
  measurement names colliding).
- Re-ingest of the same run is out of scope (runs are immutable once ingested);
  no back-fill for already-ingested runs.

## Out of scope (YAGNI)

Configurable harmonics/window for the recorded metrics (defaults only; the
interactive viewer keeps its controls); back-filling existing runs; auto-creating
default specs for the genalyzer metrics.
