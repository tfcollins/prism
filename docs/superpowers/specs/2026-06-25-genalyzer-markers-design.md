# Design: toggleable genalyzer markers on the FFT plot

Date: 2026-06-25

## Problem

A waveform case's FFT tab shows the spectrum but nothing about converter
performance. We want toggleable **genalyzer** markers on that FFT plot — the
fundamental, harmonics (HD2–HDn), DC, and worst spur — plus a metrics summary
(SNR / SFDR / SINAD / THD / ENOB), computed with the real ADI genalyzer library.

## Decisions (from brainstorming)

- **Compute source:** the real genalyzer library — its C lib (`libgenalyzer`)
  is built into the api image and CI (the pip wheel is pure-Python ctypes
  bindings and does not bundle the native lib).
- **Target figure:** the FFT plot (computed from waveform artifacts) only.
- **Toggle content:** labeled markers **and** a metrics summary panel.

## Genalyzer Python API (reference)

`import genalyzer as gn`. Configure a Fourier-analysis object then run analysis:

- `gn.fa_create(key)`, `gn.fa_fixed_tone(key, "A", gn.FaCompTag.SIGNAL, freq, ssb)`,
  `gn.fa_hd(key, n)` (harmonic order), `gn.fa_fsample(key, fs)`, `gn.fa_fdata(...)`.
- FFT: `gn.fft(...)` (or the real-input variant) → complex FFT array.
- `results = gn.fft_analysis(key, fft_cplx, nfft, axis_type)` → dict with:
  - metrics: `fsnr`, `snr`, `sfdr`, `sinad`, `thd`, `enob`;
  - tones: `A:freq` / `A:mag_dbfs` (fundamental), `2A:…` / `3A:…` (harmonics),
    `dc:mag_dbfs`, and `maxspurindex` (worst spur bin).

Exact calls (real vs complex FFT, axis types, manager vs key config, precise
result keys) are finalized against the installed library during implementation —
**step 0 below verifies them on a synthetic tone before anything is built on
top.**

## Step 0 — de-risk the build (do first)

Before writing wrapper/endpoint/UI code:

1. Build `libgenalyzer` locally (`cmake`, `g++`, `libfftw3-dev`); install
   `genalyzer` from PyPI into the api venv.
2. Confirm `import genalyzer as gn` works and `gn.fft_analysis` returns sane
   numbers for a synthetic full-scale sine (fundamental near the tone freq,
   high SNR). Capture the exact API shape used by the wrapper.

If the source build is troublesome, stop and report before proceeding.

## Infrastructure

### Dependency

Add `genalyzer` to `apps/api` `pyproject.toml`. It is untyped → add to the mypy
`ignore_missing_imports` overrides (alongside celery/h5py/boto3/scipy).

### api Dockerfile (multi-stage)

- **builder** (`python:3.12-slim`): `apt-get install -y --no-install-recommends
  git cmake g++ libfftw3-dev`; clone `analogdevicesinc/genalyzer` at a tag
  compatible with the pip `genalyzer` version; `cmake -B build -S .` (library
  only, tests/examples off), `cmake --build build`, `cmake --install build`
  → `/usr/local/lib/libgenalyzer.so*`.
- **runtime** (existing stage): `apt-get install -y --no-install-recommends
  libfftw3-3`; `COPY --from=builder /usr/local/lib/libgenalyzer.so* /usr/local/lib/`;
  `RUN ldconfig`. Then the existing `uv pip install --system .` (which now pulls
  the `genalyzer` pip package). hadolint-clean (pin apt or `# hadolint ignore`
  as the existing file already does for pip).

### CI — `test-backend.yml`

Add a step before `pytest` that builds + installs `libgenalyzer` (apt build
deps + cmake build), wrapped in `actions/cache` keyed on the pinned genalyzer
version so it's built once. The lint job (`lint.yml`) is unchanged — ruff/mypy
don't load the native lib (mypy ignores the import), and the pure-Python pip
package installs without it.

## Backend — analysis

### `dsp/genalyzer_markers.py`

```python
@dataclass
class Marker:
    label: str          # "Fund", "HD2", … "DC", "Worst spur"
    frequency: float    # Hz
    mag_dbfs: float

@dataclass
class GenalyzerResult:
    markers: list[Marker]
    snr: float | None
    sfdr: float | None
    sinad: float | None
    thd: float | None
    enob: float | None
    fsnr: float | None

def analyze(samples: np.ndarray, sample_rate: float, *, harmonics: int = 5) -> GenalyzerResult: ...
```

Wraps the genalyzer calls; converts the results dict into `markers` (Fund, HD2…
HDn, DC, worst spur with their frequency + `mag_dbfs`) and the metric fields.
Missing/None metrics are tolerated. Unit-tested on a synthetic tone.

### Endpoint — `GET /artifacts/{id}/genalyzer?harmonics=N`

Mirrors the FFT endpoint: load the waveform (`load_waveform`), run `analyze`,
and cache the JSON result as a `DerivedArtifact` keyed by `(source_hash,
params_hash(harmonics))` so repeat calls are served from cache. New
`GenalyzerResponse` schema:

```python
class GenalyzerMarker(BaseModel):
    label: str
    frequency: float
    mag_dbfs: float

class GenalyzerResponse(BaseModel):
    markers: list[GenalyzerMarker]
    snr: float | None = None
    sfdr: float | None = None
    sinad: float | None = None
    thd: float | None = None
    enob: float | None = None
    fsnr: float | None = None
```

`harmonics` is bounded (e.g. `ge=1, le=10`). A non-waveform artifact → 400, as
the other DSP endpoints do.

## Frontend

- `types.ts` — `GenalyzerMarker`, `GenalyzerResponse`.
- `queries.ts` — `useGenalyzer(artifactId, enabled)` →
  `GET /artifacts/:id/genalyzer`, lazy (`enabled`), cached by react-query.
- `FFTPlot.tsx` — add a **"genalyzer markers"** toggle (same control style as
  SpectrumAnalysis's "detect spurs"). Off by default. When on:
  - overlay a Plotly `markers+text` trace at each marker's
    `(frequency, mag_dbfs)`, labeled `Fund`/`HD2`/…/`DC`/`Worst spur`;
  - render a compact metrics panel below the plot: SNR, SFDR, SINAD, THD, ENOB
    (each value or "—" when null).
  - loading/error states inline; the toggle stays usable.

Marker y-values are genalyzer dBFS; if they read as offset from the Welch trace
the implementation may instead draw vertical reference lines — the labels +
metrics are the authoritative content either way.

## Testing

- **Backend:**
  - `dsp/genalyzer_markers` on a synthetic full-scale sine at a known freq → a
    `Fund` marker within one bin of the tone; `snr`/`enob` present and sane;
    at least one harmonic marker present.
  - endpoint: waveform artifact → 200 with markers + metrics; second call hits
    the derived-artifact cache (assert no recompute, mirroring the FFT cache
    test); non-waveform artifact → 400.
- **Frontend:** `FFTPlot` test — markers toggle off → no marker text / metrics;
  toggle on with a mocked `useGenalyzer` → marker labels (e.g. "Fund", "HD2")
  and the SNR/SFDR values render.

## Error handling / edge cases

- genalyzer raising on degenerate input (silence, too-short capture) → the
  endpoint returns an empty-markers / null-metrics result rather than 500.
- libgenalyzer missing at runtime (shouldn't happen in the image) surfaces as an
  import error at app start, not per-request.

## Limitations

- The C-lib build pins a genalyzer tag compatible with the pip package; a future
  pip bump must move the tag too.
- Real-input vs complex-input FFT handling and the precise tone/result keys are
  locked in at step 0 against the installed library.
