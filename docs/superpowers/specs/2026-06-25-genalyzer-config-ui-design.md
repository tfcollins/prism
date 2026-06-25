# Design: genalyzer config UI (harmonics + window)

Date: 2026-06-25

## Problem

The genalyzer FFT markers feature analyzes with a fixed Blackman-Harris window
and a default harmonic count. Users want to tune the analysis: choose the FFT
**window** and the number of **harmonics** from the UI.

## Context

- `dsp/genalyzer_markers.analyze(samples, sample_rate, *, harmonics=5)` hardcodes
  `gn.Window.BLACKMAN_HARRIS`.
- `GET /artifacts/{id}/genalyzer?harmonics=N` caches a `DerivedArtifact` keyed by
  `h{harmonics}`.
- `FFTPlot` has a "genalyzer markers" toggle + metrics panel; `useGenalyzer`
  sends no tunables.
- genalyzer exposes exactly three windows: `BLACKMAN_HARRIS`, `HANN`,
  `NO_WINDOW`.

## Backend

### `dsp/genalyzer_markers.py`

`analyze(samples, sample_rate, *, harmonics=5, window="blackman_harris")`.

- A module map turns the window string into `gn.Window`:
  `{"blackman_harris": BLACKMAN_HARRIS, "hann": HANN, "none": NO_WINDOW}`,
  defaulting to `BLACKMAN_HARRIS` for any unknown value.
- Single-side-bin (`ssb`) depends on the window: **0 for `NO_WINDOW`** (which
  assumes coherent sampling — no leakage skirts to exclude) and **3** for the
  windowed cases, applied to both `fa_max_tone` and `fa_ssb(DEFAULT, …)`. This
  keeps SNR/SFDR/etc sensible across windows.

### Endpoint `GET /artifacts/{id}/genalyzer`

- Add `window: str = Query(default="blackman_harris")`. Validate against the
  three accepted names (`blackman_harris`, `hann`, `none`); anything else → 400.
- Cache key becomes `h{harmonics}-{window}` so each `(harmonics, window)` pair
  caches independently.
- Pass `window` through to `analyze`.

### Tests

- Wrapper: `window="hann"` and `window="none"` both return a `Fund` marker near
  the tone and present metrics; an unknown window falls back (no raise).
- Endpoint: `?window=hann&harmonics=3` → 200 with markers; a second identical
  call hits the cache; `?window=blackman_harris` (different) computes separately;
  `?window=bogus` → 400.

## Frontend

### `useGenalyzer`

`useGenalyzer(artifactId, enabled, harmonics, window)` — sends `harmonics` and
`window` as query params and includes both in the query key, so changing either
refetches.

### `FFTPlot`

When the **genalyzer markers** toggle is on, render an inline config row:

- **Harmonics** — a stepper/number input bounded 1–10 (default 5).
- **Window** — a select: Blackman-Harris (default), Hann, None.

State (`harmonics`, `window`) lives in `FFTPlot`; changing a control re-runs
`useGenalyzer` and re-overlays the markers + metrics. Controls are hidden when
the toggle is off.

### Test

`FFTPlot` (Plotly mocked, `useGenalyzer` mocked to capture args): toggle on →
the Harmonics and Window controls render; selecting a different window /
harmonics value re-invokes `useGenalyzer` with the new args.

## Error handling / edge cases

- Unknown window at the API boundary → 400; in the wrapper (defensive) →
  Blackman-Harris fallback.
- `NO_WINDOW` on a non-coherent capture yields leakage-degraded metrics; this is
  inherent to the choice, surfaced by letting the user pick it. No special
  handling beyond `ssb=0`.

## Out of scope (YAGNI)

No nfft/navg/averaging controls, no per-project saved defaults, no windows
beyond genalyzer's three.
