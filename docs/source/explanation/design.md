# Design decisions

A few choices shape how Prism behaves; this page explains the *why* behind them.

## Why Prism exists

When a test suite produces *both* pass/fail outcomes **and** signal data — DSP
pipelines, RF benches, audio codecs — most CI dashboards keep the pass/fail and
discard the signal. That signal is exactly what you need to *diagnose* a
failure rather than just observe it. Prism stores the artifacts alongside the
metadata, makes them browsable, and lets you overlay them across runs.

## Content-addressed artifacts

Artifact bytes are stored in MinIO under sha256-keyed paths, so identical bytes
across many runs share a **single** object. A nightly job that re-uploads an
unchanged golden waveform every night costs one stored copy, not thirty.

The `artifacts` table uses a polymorphic `owner_type` discriminator
(run / suite / case) rather than three near-identical nullable FK columns. One
table, one code path, three owners.

`DerivedArtifact` extends the same idea to *computed* views: an FFT is cached
under `(source_hash, params_hash)`, so the first request for a given
window/nfft/overlap computes and stores a `.npz`, and every later request with
the same parameters is a cache hit. Waveform downsampling, by contrast, is cheap
and computed on the fly.

## Read-time spec evaluation

Spec limits on a measurement (`spec_min` / `spec_max`) are **optional**, and
pass/fail plus the signed **margin** are derived *when the measurement is read*,
not stored at ingest. This means re-speccing a project — tightening an ACPR
limit, say — instantly re-colours all historical runs against the new limit
without rewriting a single stored row. Project-level `spec_definitions` fill in
limits for runs that arrived without their own.

## One upload, one suite

The canonical shape is **one JUnit upload == one `TestRun` == one
`TestSuite`**. The `TestRun` is the atomic unit of an upload (metadata +
artifacts committed together); the `TestSuite` holds the aggregate counts.
Multi-suite uploads are accepted for flexibility, but the dashboard is designed
around the one-suite form — it's what makes the Suite column and the flattened
case list read cleanly. See {doc}`../reference/file-conventions`.

## Configuration

All runtime config is `PRISM_*` environment variables consumed by
`prism_api.config.Settings` (pydantic-settings), with `get_settings()` cached.
`JWT_SECRET` is validated at startup (≥32 chars) so a misconfigured deployment
fails fast rather than silently issuing weak tokens.
