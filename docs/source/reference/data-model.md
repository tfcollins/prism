# Data model

```{mermaid}
erDiagram
    User ||--o{ TestRun : uploads
    Project ||--o{ TestRun : groups
    TestRun ||--o{ TestSuite : contains
    TestRun ||--o{ RunTag : "k/v tags"
    TestSuite ||--o{ TestCase : contains
    TestCase ||--o{ Artifact : attaches
    TestRun ||--o{ Artifact : attaches
    TestSuite ||--o{ Artifact : attaches
    Artifact ||--o{ DerivedArtifact : caches
    TestCase ||--o{ Measurement : has
```

## Canonical mapping

**One JUnit upload == one `TestRun` == one `TestSuite`.** The `TestRun` row
exists so ingest can atomically commit the parsed contents plus any artifacts
from the upload archive; the `TestSuite` row holds the aggregate pass/fail
counts and ancestry for its `TestCase` rows. In practice a JUnit file with a
single `<testsuite>` is the shape the UI assumes.

Multi-`<testsuite>` uploads are also supported (each `<testsuite>` becomes a
separate `TestSuite` under the same `TestRun`). The dashboard renders them as a
list of suite-name badges per run; the run-detail page keeps the expandable
tree rather than flattening.

## Tables

| Table | Purpose |
|---|---|
| `users` | Authentication; flat permission model |
| `projects` | Top-level grouping, slug + name |
| `test_runs` | One per upload; tracks ingest status, links project + creator |
| `run_tags` | Arbitrary key/value tags on a run (branch, sha, hardware) |
| `test_suites` | Per-`<testsuite>` aggregates within a run |
| `test_cases` | Individual case + outcome + failure detail |
| `artifacts` | File metadata (kind, hash, MinIO key); polymorphic owner (run/suite/case) |
| `derived_artifacts` | Cached computations (FFT) keyed by source + params |

Further tables back the RF and workflow features: `measurements` (named numeric
results on a case), `spectrum_masks` (project emission-mask limit lines),
`spec_definitions` (project per-measurement limits applied at read time when a
run carried none), `saved_views` (named dashboard filter sets), and
`audit_events` (who uploaded / edited specs / set calibration). `test_runs`
also carries a nullable `calibration_run_id` self-reference linking a
measurement run to the calibration that defined its corrections.

## Measurements

A `measurement` is a named numeric value attached to a `TestCase` — channel
power, ACPR, SNR, etc. Spec limits (`spec_min` / `spec_max`) are optional; the
API derives pass/fail and the **margin** (signed distance to the nearest limit)
at read time rather than storing them, so re-speccing a project never requires
rewriting historical rows.

Measurements arrive automatically from JUnit `<properties>` using the
convention `{name}` for the value plus `{name}__unit` / `{name}__min` /
`{name}__max`. See {doc}`../how-to/record-measurements`.

## Spectra

A spectrum is a `(frequency, power)` trace plotted on the analyzer view, with
channel-power / ACPR / OBW, spur detection, and mask overlays computed from it.
Two upload formats are detected automatically:

- **CSV** (`spectrum_csv`) — two columns `frequency,power` with optional
  `# key=value` metadata comments (`center`, `span`, `rbw`, `vbw`, `ref_level`,
  `unit`, `detector`, `sweep_time`).
- **Touchstone** (`spectrum_touchstone`, `.s1p` / `.s2p`) — an S-parameter
  export. The transmission magnitude is surfaced as the trace: `S21` for a
  2-port and `S11` for a 1-port; the `MA`, `DB`, and `RI` data formats are all
  converted to dB. Phase is discarded.

## Artifacts are content-addressed

Identical bytes across runs share one MinIO object, keyed by sha256. The
polymorphic `owner_type` discriminator (run / suite / case) avoids three
near-identical FK columns. `DerivedArtifact` caches computed views (such as the
Welch FFT) keyed by `(source_hash, params_hash)`. See
{doc}`../explanation/design`.
