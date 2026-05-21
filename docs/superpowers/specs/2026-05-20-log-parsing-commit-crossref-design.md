# Log parsing & commit cross-reference — design

## Context

Prism ingests boot/dmesg logs (`boot.log`, `dmesg_*`, `iio_info.txt`, …) as
run- or case-scoped `LOG_TEXT` artifacts. Today nothing parses their contents:
they are stored in MinIO and only viewable as a raw download / iframe, and the
kernel/HDL commit a run was tested against is only known if a human set it as a
run tag.

On an ADI/IIO bench, the boot log is the record of *what build was under test*
(kernel commit + HDL/FPGA commit) and *whether bringup was healthy* (errors,
warnings, kernel panics, failed driver probes). This feature parses those logs
at ingest into structured, queryable facts and makes commits first-class so
runs can be cross-referenced by the build they exercised.

Outcome: every run surfaces its kernel/HDL commits, kernel version, board, and
error/warning/panic tallies; you can list all runs at a given commit, jump
between runs that share a build, diff commits + log health in Compare, and click
a commit straight through to its upstream git repo.

## Scope

In scope (all confirmed with the user):

- Extract per boot/dmesg log: **kernel commit** and **HDL commit** (two distinct
  hashes per boot), **kernel version**, **board/model**, **error/warning
  tallies + a capped sample of lines**, **panic/oops/call-trace** flag, and
  **failed driver/probe** lines.
- Cross-reference: **all runs at a commit**, **shared-commit links on a run**,
  **commit deltas + log diffs in Compare**, **link-out to git repos**.

Out of scope: log parsing for non-boot artifacts beyond generic severity
tallies; alerting/notifications on findings; per-line full-text search.

## Architecture

Chosen approach: **parse at ingest, persist structured findings** (Approach A
from brainstorming). Parsing on demand was rejected because "all runs at commit
X" would otherwise require scanning every run's logs per query. Indexed commit
columns make cross-reference a cheap join, and stored findings let Compare diff
two runs without re-fetching blobs. Findings are frozen at ingest, consistent
with how Prism freezes the rest of a run.

### Data model

New module `apps/api/src/prism_api/models/log.py`, Alembic migration `0011`,
registered in `models/__init__.py`.

`log_reports` — one row per parsed boot/dmesg `LOG_TEXT` artifact:

| column          | type            | notes                                  |
| --------------- | --------------- | -------------------------------------- |
| id              | str(36) PK      | uuid                                   |
| run_id          | str(36) FK      | → test_runs, ON DELETE CASCADE, index  |
| artifact_id     | str(36)         | source artifact                        |
| source          | str(512)        | filename (e.g. `boot.log`)             |
| kernel_version  | str(255) null   | from `Linux version …`                 |
| board           | str(255) null   | from `Machine model:` / `Hardware name:` |
| kernel_commit   | str(64) null    | indexed                                |
| hdl_commit      | str(64) null    | indexed                                |
| error_count     | int             |                                        |
| warn_count      | int             |                                        |
| has_panic       | bool            |                                        |
| created_at/updated_at | datetime  | TimestampMixin                         |

`log_findings` — capped sample of notable lines (default ≤200 per report):

| column         | type          | notes                                       |
| -------------- | ------------- | ------------------------------------------- |
| id             | str(36) PK    |                                             |
| log_report_id  | str(36) FK    | → log_reports, ON DELETE CASCADE, index     |
| severity       | str(16)       | `error` / `warn` / `panic` / `probe_fail`   |
| line_no        | int null      | line number in the log                      |
| text           | str(1000)     | truncated line text                         |

### Parser

`apps/api/src/prism_api/parsers/logs.py` — pure and unit-testable:

```python
@dataclass
class ParsedFinding:
    severity: str          # error|warn|panic|probe_fail
    line_no: int | None
    text: str

@dataclass
class ParsedLog:
    kernel_version: str | None
    board: str | None
    kernel_commit: str | None
    hdl_commit: str | None
    error_count: int
    warn_count: int
    has_panic: bool
    findings: list[ParsedFinding]

def parse_log(
    data: bytes, *, kernel_pattern: str, hdl_pattern: str, findings_cap: int
) -> ParsedLog: ...
```

Behavior:

- **Commits** — `kernel_pattern` / `hdl_pattern` regexes; the first capture group
  is the hash. Configurable so exact wording can change without code edits.
- **Version / board** — `Linux version (\S+)`; board from `Machine model:` or
  `Hardware name:`.
- **Severity classification**, in priority order, handling optional dmesg
  `[   12.345678]` prefixes and bare text:
  - `panic` — `Kernel panic`, `Oops`, `BUG:`, `Call Trace` (also sets `has_panic`)
  - `error` — syslog `<3>`/`<2>`/`<1>`/`<0>`, or `error`/`fail` keywords
  - `warn` — syslog `<4>`, or `warn` keyword
  - `probe_fail` — `probe failed`, `failed to`, `timeout`
  - `error_count`/`warn_count` tally all matching lines; `findings` holds the
    capped sample (errors/panics prioritized when truncating).

### Configuration (`config.Settings`, all `PRISM_*`)

- `LOG_KERNEL_COMMIT_PATTERN`, `LOG_HDL_COMMIT_PATTERN` — extraction regexes with
  ADI-style defaults (to be confirmed against a real boot log during
  implementation).
- `KERNEL_REPO_URL`, `HDL_REPO_URL` — base URLs for the link-out feature; a
  commit URL is `f"{base}/commit/{hash}"` when the base is set.
- `LOG_FINDINGS_CAP` — default 200.

### Ingest & backfill

- `ingest.py`: after a `LOG_TEXT` artifact is attached, call `parse_log` with the
  configured patterns and persist a `LogReport` + `LogFinding`s via a new
  `repos/logs.py` `LogRepo`. Works through the existing inline `patch_ingest`
  seam used in tests.
- Backfill CLI `prism-api reparse-logs` (in `cli.py`): iterate existing
  `LOG_TEXT` artifacts, (re)build their reports — for runs ingested before this
  feature, and after a pattern change.

## API

Extends existing routers; no new top-level router needed.

- `GET /runs/{id}/logs` → `list[LogReportOut]` (version, board, both commits +
  derived `kernel_commit_url` / `hdl_commit_url`, counts, `has_panic`, findings
  sample). One row per parsed `LOG_TEXT` artifact, so a run may have several
  (e.g. `boot.log` + `dmesg` + `iio_info.txt`); reports with no commits/version
  (like `iio_info.txt`) are still listed for their tallies.
- A compact **boot summary** is folded onto `RunDetail` so the run page renders
  without a second request. With multiple reports it is resolved
  deterministically: `kernel_commit` / `hdl_commit` / `kernel_version` / `board`
  are taken from the first report (oldest by `created_at`) that has each field
  set; `error_count` / `warn_count` are summed across reports; `has_panic` is
  any. This keeps the summary stable when a run carries both a boot log and a
  separate dmesg dump.
- `GET /projects/{slug}/commits?type=kernel|hdl` → `[{commit, run_count}]` for
  the commit-centric view.
- `GET /runs` gains `kernel_commit` / `hdl_commit` query filters, reusing the
  tag-filter join pattern already added for DUT navigation.
- Boot summary carries `shared_kernel_count` / `shared_hdl_count` (count of other
  runs in the project sharing each commit) to drive the "N runs on this build"
  links.
- `CompareResponse` gains a per-run boot block (commits, version, counts) plus a
  small diff (commit deltas, error/warn count deltas).

`LogReportOut` (schema) derives commit URLs from settings: null when no repo
base is configured.

## UI (`apps/web`)

- **RunDetail** — a **Boot panel**: kernel version, board, kernel + HDL commit as
  repo links, error/warn tallies, a prominent banner when `has_panic`; an
  expandable findings list filterable by severity; "N runs share this
  kernel/HDL commit" links into the filtered runs list.
- **ProjectDashboard** — a **Commits tab**: kernel/HDL commits with run counts;
  clicking filters the Runs tab by that commit (same mechanism as the DUT/tag
  filter).
- **Compare** — the commit-delta + count-diff block above the existing case
  table.

New react-query hooks in `api/queries.ts` (`useRunLogs`, `useCommits`,
`useRunsByCommit`) mirror existing hook patterns; types in `api/types.ts`.

## Error handling

- A log that matches no commit pattern yields a `LogReport` with null commits and
  still-valid counts — never an ingest failure.
- Parsing is best-effort: a parser exception on one artifact is logged and
  skipped so it cannot fail the whole run ingest.
- Non-UTF8 bytes decode with `errors="replace"` (matches existing parsers).
- Commit URLs are null (plain text, not links) when repo bases are unset.

## Testing

- **Parser unit tests** against `dmesg` fixtures: both commits present/absent,
  kernel panic, severity tallies, probe-fail detection, cap enforcement, and
  dmesg-prefix vs bare-text lines.
- **API tests**: commit listing + run counts, run filter by commit,
  `GET /runs/{id}/logs`, Compare boot block, and the `reparse-logs` backfill CLI.
- **Web tests**: pure helpers (commit-URL building, severity formatting). Panels
  follow existing component patterns.
- Migration `0011` validated offline against the postgres dialect, as with prior
  migrations.

## Implementation staging

1. Parser + model/migration + config + ingest wiring + backfill CLI — delivers
   extraction immediately (commits/version/board/counts visible via API).
2. Cross-reference endpoints + Compare extension.
3. UI surfaces (Boot panel, Commits tab, Compare block).

## Critical files

- New: `models/log.py`, `parsers/logs.py`, `repos/logs.py`,
  `schemas/log.py`, `migrations/versions/0011_log_reports.py`.
- Modified: `ingest.py`, `cli.py`, `config.py`, `routers/runs.py`,
  `routers/projects.py`, `routers/compare.py`, `schemas/run.py`,
  `schemas/compare.py`.
- Web: `api/types.ts`, `api/queries.ts`, `pages/RunDetailPage.tsx`,
  `pages/ProjectDashboardPage.tsx`, `pages/ComparePage.tsx`, and new Boot-panel /
  commits-tab components.

## Verification

- Upload a run whose archive includes a boot log with known kernel + HDL commits,
  a panic, and several warnings; confirm the run's Boot panel shows both commits
  (as repo links), version/board, and correct tallies, with the panic banner.
- Upload a second run at the same kernel commit; confirm "1 run shares this
  kernel commit" links to it, and the Commits tab lists the commit with
  run_count 2 and filters the runs list when clicked.
- Compare the two runs; confirm the commit-delta/count-diff block.
- Run `prism-api reparse-logs` against a pre-feature run and confirm its report
  appears.
- `make lint` and `make test` clean; migration `0011` offline SQL validates.
