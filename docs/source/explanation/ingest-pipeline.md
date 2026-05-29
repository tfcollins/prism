# The ingest pipeline

Ingest in Prism is **asynchronous**. The upload request does the minimum needed
to durably accept the bytes, then hands off to a background worker. This keeps
uploads fast and lets parsing, archive extraction and DSP run without blocking
the HTTP client.

```{mermaid}
sequenceDiagram
    participant B as Browser / CI
    participant A as api (FastAPI)
    participant M as minio
    participant R as redis
    participant W as worker (Celery)
    B->>A: POST /api/v1/runs (junit + zip + metadata)
    A->>A: insert TestRun(status=pending)
    A->>M: upload bytes under sha256 keys
    A->>R: dispatch prism.ingest_run
    A-->>B: 202 + run id (pending)
    R->>W: deliver task
    W->>M: fetch blobs
    W->>W: parse JUnit, walk archive, detect kinds
    W->>A: write suites / cases / artifacts; set final status
    B->>A: GET /api/v1/runs/{id} (poll)
    A-->>B: status pass / fail / mixed / error
```

## On upload

1. The browser (or `upload_run.py`) POSTs `multipart/form-data` to `api`: a
   JUnit XML, an optional zip, and a JSON `metadata` part. The `X-Prism-Csrf`
   header must match the `prism_csrf` cookie issued at login.
2. `api` writes a `TestRun(status=pending)` row, uploads the JUnit XML and (if
   present) the zip to MinIO under content-addressed keys, and dispatches
   `prism.ingest_run` to Celery via Redis.
3. `worker` pulls the task, fetches the blobs from MinIO, parses JUnit with
   `junitparser`, extracts the zip, identifies each file's kind via magic bytes
   + extension (`prism_api.parsers.detect`), and attaches each file to its
   run / suite / case via the `{suite}__{case}__{label}` filename convention.
   It then sets the run's final `status` (pass / fail / mixed / error).
4. The browser polls `GET /api/v1/runs/{id}` to watch the status flip from
   `pending`.

:::{note}
Tests run ingest **inline** (no broker) via the `patch_ingest` fixture in
`tests/conftest.py`, so the parsing path is exercised end-to-end without
standing up Redis or Celery.
:::

## On plot view

1. The browser navigates to a case → `GET /api/v1/cases/{id}`, which returns
   its attached `Artifact` rows.
2. For a **waveform**, the browser calls
   `GET /api/v1/artifacts/{id}/waveform?downsample=N`. The api fetches the raw
   bytes from MinIO, parses them with the right loader, runs
   `downsample_for_plot`, and returns JSON samples. Downsampling is computed on
   the fly from `prism_api.dsp.downsample`.
3. For an **FFT**, the browser calls
   `GET /api/v1/artifacts/{id}/fft?window=&nfft=&overlap=`. The api looks up a
   `DerivedArtifact` by `(source_hash, params_hash)`. On a cache hit it loads
   the `.npz` from MinIO; on a miss it computes a Welch FFT, stores the `.npz`,
   creates the `DerivedArtifact` row, and returns JSON.
