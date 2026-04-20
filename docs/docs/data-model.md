# Data model

```
User
Project ─< TestRun ─< TestSuite ─< TestCase
              │                       │
              ├─< RunTag (k/v)        │
              └─< Artifact >──────────┘
                     │
                     └─< DerivedArtifact (FFT cache, thumbnails)
```

| Table             | Purpose |
|-------------------|---------|
| `users`           | Authentication; flat permission model |
| `projects`        | Top-level grouping, slug + name |
| `test_runs`       | One per upload; tracks ingest status, links project + creator |
| `run_tags`        | Arbitrary key/value tags on a run (branch, sha, hardware) |
| `test_suites`     | Per-suite aggregates within a run |
| `test_cases`      | Individual case + outcome + failure detail |
| `artifacts`       | File metadata (kind, hash, MinIO key); polymorphic owner (run/suite/case) |
| `derived_artifacts` | Cached computations (FFT) keyed by source + params |

Artifacts are content-addressed: identical bytes across runs share one MinIO object. The polymorphic `owner_type` column avoids three near-identical FK columns.
