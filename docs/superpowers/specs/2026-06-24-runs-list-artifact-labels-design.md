# Design: example boot logs + figure/boot-log labels on the runs list

Date: 2026-06-24

## Problem

Two gaps in the demo experience:

1. The boot/dmesg log feature (`parsers/logs.py` → `LogReport` → boot summary,
   commit cross-referencing) has no demo data. `scripts/seed_demo.py` attaches
   waveform CSVs but never a log file, so a fresh stack never shows a parsed
   boot log.
2. The per-project runs list (`RunsTable`) shows status, suite, pass/fail,
   when, and tags — but nothing about what artifacts a run carries. You cannot
   tell at a glance which runs have plottable figures or a boot log without
   opening each run.

## Goals

- Seed example runs that carry a boot log, so the boot-log/commit features are
  visible in the demo.
- Surface, on each row of the project runs list, whether the run has figures
  and/or a boot log.

## Non-goals (YAGNI)

- No database migration (the flags are computed per request, not stored).
- No new `ArtifactKind` values, and no rework of Plotly-figure-JSON detection
  (those arrive as `log_text` today — see "Limitations").
- No labels on the Overview or Search lists — project dashboard only.
- No changes to `RunDetailPage`.

## Definitions

- **Figure / plottable artifact**: an artifact whose kind is one of
  `waveform_csv`, `waveform_hdf5`, `waveform_npy`, `spectrum_csv`,
  `spectrum_touchstone`, `spectrogram`, `image_png`. This is the broad
  "anything the run can plot" reading. It deliberately **excludes** `wav_audio`
  (rendered as an audio player, not a plot) and Plotly figure JSON stored as
  `log_text`.
- **Boot log**: a run that has at least one parsed `LogReport`. Boot logs are
  produced during ingest whenever a `LOG_TEXT` artifact is found in the upload
  archive (`ingest.py` calls `parse_log` → `LogRepo.create_report`).

## Part A — Backend: per-run `has_figures` / `has_boot_log` flags

### Schema

`apps/api/src/prism_api/schemas/run.py` — add to `RunListItem`:

```python
has_figures: bool = False
has_boot_log: bool = False
```

Defaults keep existing callers/tests valid.

### Repo helpers

`apps/api/src/prism_api/repos/runs.py` — two batch methods, each computed once
for the whole page (the list endpoint is already N+1 over counts/tags/suites,
but these new lookups are explicitly batched to avoid adding more per-row
queries). Both guard empty input:

```python
def runs_with_boot_log(self, run_ids: list[str]) -> set[str]:
    if not run_ids:
        return set()
    rows = self._session.execute(
        select(LogReport.run_id).where(LogReport.run_id.in_(run_ids)).distinct()
    ).scalars()
    return set(rows)
```

`runs_with_figures` must resolve artifacts that may be owned at run, suite, or
case scope (`Artifact.owner_type` / `Artifact.owner_id` is a polymorphic
discriminator, not an FK). Algorithm (3 queries total, independent of row
count):

1. `suites = select(TestSuite.id, TestSuite.run_id).where(run_id IN ids)` →
   build `suite_to_run`.
2. `cases = select(TestCase.id, TestCase.suite_id).where(suite_id IN suite_ids)`
   → build `case_to_run` (via `suite_to_run`).
3. `arts = select(Artifact.owner_type, Artifact.owner_id).where(
   Artifact.kind IN FIGURE_KINDS AND Artifact.owner_id IN (run_ids + suite_ids
   + case_ids))`. For each row, map `owner_id` back to a run id:
   - `owner_type == "run"` → `owner_id` itself (if in `run_ids`)
   - `owner_type == "suite"` → `suite_to_run[owner_id]`
   - `owner_type == "case"` → `case_to_run[owner_id]`

   Collect into a `set[str]` of run ids.

`FIGURE_KINDS` is a module-level frozenset of the `ArtifactKind` values listed
under Definitions. Add the needed imports (`TestSuite`, `TestCase`, `Artifact`,
`ArtifactKind`) to the repo.

### Endpoint

`apps/api/src/prism_api/routers/runs.py` `list_runs` — after fetching `items`,
compute once:

```python
ids = [r.id for r in items]
fig_ids = runs.runs_with_figures(ids)
boot_ids = runs.runs_with_boot_log(ids)
```

then set `has_figures=r.id in fig_ids`, `has_boot_log=r.id in boot_ids` on each
`RunListItem`.

## Part B — Frontend: labels in `RunsTable`

### Types

`apps/web/src/api/types.ts` — add `has_figures: boolean` and
`has_boot_log: boolean` to the `RunListItem` type.

### Table

`apps/web/src/components/RunsTable.tsx`:

- Add an **"Artifacts"** column header after "Suite" and before "Pass".
- In the cell, render compact Chakra `Badge`s wrapped in `Tooltip`, each with an
  `aria-label` (the e2e suite asserts no serious/critical axe violations):
  - `has_figures` → `Badge` "Figures" (e.g. `colorPalette="purple"`), tooltip
    "Run has plottable artifacts (waveforms, spectra, images)".
  - `has_boot_log` → `Badge` "Boot log" (e.g. `colorPalette="gray"`), tooltip
    "Run has a parsed boot/dmesg log".
  - Neither → faint em-dash, matching the existing empty-suite treatment.

No icon library exists in `apps/web`, so labels are text badges (consistent with
the existing suite badges).

## Part C — Demo seed: boot logs on `kuiper-linux` runs

`scripts/seed_demo.py` (must stay standard-library only):

- Add `_boot_log(board, kernel_commit, hdl_commit, *, errors, warns, panic)`
  returning dmesg-style `str` containing:
  - `Linux version 6.1.0-g<kernel_commit> (...)` → parser fills
    `kernel_version` + `kernel_commit` (trailing `-g<sha>`).
  - `Machine model: <board>` → parser fills `board`.
  - a line matching the HDL pattern `(?i)hdl.*?([0-9a-f]{7,40})`, e.g.
    `fpga_manager fpga0: HDL ... <hdl_commit>` → `hdl_commit`.
  - normal boot lines, plus `errors` error lines / `warns` warn lines /
    optional `Kernel panic - not syncing: ...` when `panic`.
- Extend `build_kuiper_runs` so each entry builds an archive containing a
  run-scoped `boot.log` (a bare filename does not match the
  `{suite}__{case}__{label}` convention, so `_resolve_owner` attaches it to the
  run). Severity scales with the entry's expected status:
  - `pass` → clean log (0 errors, 0 warns, no panic).
  - `fail` → a couple of error lines + a probe failure; the `ad9371`/`zc706`
    fail entry additionally gets a kernel panic to exercise `has_panic`.
  - `mixed` → one or two warn lines.
- Choose deterministic kernel/HDL commits with some shared across entries so the
  existing shared-kernel / shared-hdl cross-reference counts have data.
- Update the kuiper upload print line to note that a boot log is attached.

This makes the kuiper runs show **both** a boot-log badge (Part B) and the boot
summary / commit cross-ref features on the run detail page. The kuiper runs do
**not** get a figures badge (no plottable artifacts), and the `dsp-*` runs
continue to get a figures badge (waveform CSVs) but no boot-log badge — so the
demo shows every combination.

## Testing

- **Backend** (`apps/api/tests/test_runs_read.py`):
  - run uploaded with a waveform CSV → `has_figures` true, `has_boot_log` false.
  - run uploaded with an archive containing `boot.log` → `has_boot_log` true.
  - run uploaded with no archive → both false.
  - run uploaded with an `image_png` artifact → `has_figures` true (confirms the
    kind set, not just waveforms).
- **Frontend** (`apps/web/src/components/RunsTable.test.tsx`): render
  `RunsTable` with fixtures covering figures-only, boot-log-only, both, and
  neither; assert the "Figures" / "Boot log" badges appear and are absent as
  expected.

## Error handling / edge cases

- Empty run-id list → repo helpers return `set()` without querying.
- Log parse failures during ingest are already best-effort and never fail
  ingest; a run with an unparseable log simply has no `LogReport` and thus no
  boot-log badge.

## Limitations

- Plotly figure JSON is detected as `log_text` today, so it will not trigger the
  figures badge. The demo uses waveforms/images, so this does not affect the
  demo; fixing kind detection for figure JSON is out of scope.
