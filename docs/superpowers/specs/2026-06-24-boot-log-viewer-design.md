# Design: filterable, downloadable boot-log viewer

Date: 2026-06-24

## Problem

A run's boot/dmesg log is parsed into a `LogReport` (kernel/board/commits,
error/warn/panic tallies, and a capped sample of notable lines), but the only
UI surface is the compact `BootPanel` in the right sidebar, which shows the
summary plus a flat, capped findings list. You cannot read the full boot log,
filter it by severity, or download it.

## Goals

- Show the boot log in a collapsible ("accordion-like") block on the run detail
  page.
- Let the user filter the view by **Errors**, **Warnings**, or **All** dmesg
  text.
- Let the user **download** the raw boot log.

## Non-goals (YAGNI)

- In-log text search.
- Virtualized/paginated rendering beyond a simple display line cap.
- Merging multiple log files into a single combined view.

## Decisions (from brainstorming)

- **Placement:** a new full-width collapsible "Boot log" section in the main
  run-detail column. The compact summary stays in the sidebar `BootPanel`.
- **Filter source:** the browser fetches the **full raw dmesg** from the stored
  artifact and classifies/filters all three views client-side (no 200-line
  finding cap). This duplicates the parser's severity logic in TypeScript; the
  classifier is unit-tested for parity with the Python parser.

## Backend

The web cannot currently reach the raw log: `LogReportOut` omits the artifact
id. One change:

- `schemas/log.py` — add `artifact_id: str | None = None` to `LogReportOut`.
- `routers/runs.py` `get_run_logs` — populate `artifact_id=r.artifact_id` from
  the `LogReport`.

The raw bytes are already served by `GET /artifacts/{id}/raw`, which **streams
through the API** (auth via the session cookie). This is the correct source in
production, where MinIO is not browser-reachable and `/download`'s 307 to a
presigned MinIO URL would fail.

Test: `GET /runs/{id}/logs` includes `artifact_id` for a run with a boot log.

## Frontend

### Severity classifier — `lib/dmesg.ts`

Port the parser's `_classify` (`parsers/logs.py`) to TypeScript so the viewer
classifies raw lines the same way the server does:

1. strip the dmesg prefix `^\[\s*\d+\.\d+\]\s*`;
2. syslog level `<N>`: `N<=3` → error, `N==4` → warn;
3. keyword precedence: panic (`kernel panic|\bOops\b|\bBUG:|Call Trace`) →
   probe_fail (`probe failed|failed to|timeout`) → error (`error|fail`) → warn
   (`warn`); otherwise no severity (info line).

Exports:

- `type Severity = 'panic' | 'error' | 'probe_fail' | 'warn'`
- `classifyLine(raw: string): Severity | null`
- `classifyLines(text: string): { lineNo: number; severity: Severity | null; text: string }[]`
  (1-indexed by position in the full file, so filtered views keep original line
  numbers)

Filter groups: **Errors** = `{panic, error, probe_fail}`, **Warnings** =
`{warn}`, **All** = every line.

### `BootLogViewer.tsx`

A full-width collapsible "Boot log" section (Chakra `Accordion`) rendered in the
main run-detail column when the run has logs, with **one accordion item per log
report**:

- **Item header:** source filename, error/warn counts, and a panic badge when
  applicable.
- **On expand (lazy):** fetch the raw text via `useArtifactRaw(artifactId)`
  (enabled only while the item is open), then render:
  - a 3-way segmented filter **Errors / Warnings / All**;
  - the (filtered) lines in a scrollable monospace block, colored by severity
    via `severityColor`, each prefixed with its original line number; display
    capped at **5000** lines with a "…truncated — download for the full log"
    note when exceeded;
  - a **Download** control: `<a href="/api/v1/artifacts/{artifactId}/raw"
    download="{source}">` — a same-origin GET that carries the auth cookie and
    saves under the source filename.

A log report with no `artifact_id` (shouldn't happen for parsed boot logs)
renders the header only, with the body disabled and download hidden.

### Supporting changes

- `types.ts` — `LogReport` gains `artifact_id: string | null`.
- `queries.ts` — add `useArtifactRaw(artifactId, enabled)` →
  `api.get('/artifacts/{id}/raw', { responseType: 'text' })`.
- `RunDetailPage.tsx` — render `<BootLogViewer runId={...} logs={...} />` below
  the Files section (only when logs exist).
- `BootPanel.tsx` — remove the flat findings list (superseded by the viewer);
  keep the kernel/board/commits/counts summary.

## Testing

- **Backend** (`tests/test_cases_router.py` or the logs test): a run with a
  boot.log → `GET /runs/{id}/logs` returns `artifact_id` (non-null); a run
  without logs → empty list.
- **Frontend:**
  - `lib/dmesg.test.ts` — classifier unit tests mirroring the Python
    `test_parsers_logs.py` cases (panic, probe_fail, error/`fail`, warn, syslog
    levels `<3>`/`<4>`, dmesg-prefixed lines, plain info lines → null).
  - `BootLogViewer.test.tsx` — with a mocked raw-text query: Errors shows only
    error-group lines, Warnings only warn lines, All shows everything; the
    download link targets `/api/v1/artifacts/{id}/raw`.

## Error handling / edge cases

- Raw fetch pending → "Loading log…"; fetch error → an inline error with the
  download link still available.
- Empty / whitespace-only log → "No log content."
- A run with multiple log reports → one accordion item each, independently
  filtered and downloaded.

## Limitations

The TS classifier must be kept in parity with `parsers/logs.py::_classify`; the
shared test cases are the guard. Plotly-figure-JSON-as-`log_text` is unrelated
and unaffected.
