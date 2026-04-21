# Data model

```
User
Project ─< TestRun ─< TestSuite ─< TestCase
            (≡ one    (typically      │
             JUnit    one per run)    │
             upload)                  │
              │                       │
              ├─< RunTag (k/v)        │
              └─< Artifact >──────────┘
                     │
                     └─< DerivedArtifact (FFT cache, thumbnails)
```

## Canonical mapping

**One JUnit upload == one `TestRun` == one `TestSuite`.** The `TestRun` row
exists so ingest can atomically commit the parsed contents plus any
artifacts from the upload archive; the `TestSuite` row holds the aggregate
pass/fail counts and ancestry for its `TestCase` rows. In practice a JUnit
file with a single `<testsuite>` is the shape the UI assumes — a single
Test Suite Run per upload.

Multi-`<testsuite>` uploads are also supported (each `<testsuite>` becomes
a separate `TestSuite` under the same `TestRun`). The dashboard renders
them as a list of suite-name badges per run; the run-detail page keeps the
expandable tree rather than flattening.

## Tables

| Table             | Purpose |
|-------------------|---------|
| `users`           | Authentication; flat permission model |
| `projects`        | Top-level grouping, slug + name |
| `test_runs`       | One per upload; tracks ingest status, links project + creator |
| `run_tags`        | Arbitrary key/value tags on a run (branch, sha, hardware) |
| `test_suites`     | Per-`<testsuite>` aggregates within a run |
| `test_cases`      | Individual case + outcome + failure detail |
| `artifacts`       | File metadata (kind, hash, MinIO key); polymorphic owner (run/suite/case) |
| `derived_artifacts` | Cached computations (FFT) keyed by source + params |

Artifacts are content-addressed: identical bytes across runs share one MinIO
object. The polymorphic `owner_type` column avoids three near-identical FK
columns.
