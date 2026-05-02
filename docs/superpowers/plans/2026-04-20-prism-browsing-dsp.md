# Prism — Browsing & DSP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the ingested data visible. Adds waveform parsers (CSV/NPY/HDF5), server-side downsampling and FFT with `DerivedArtifact` caching, read endpoints for runs/suites/cases/artifacts, and the frontend to browse runs and plot time-domain + FFT views.

**Architecture:** Backend grows a `dsp/` module (downsample + Welch FFT via scipy) and `parsers/waveform.py` that returns `numpy.ndarray` plus sample-rate metadata. Read endpoints return JSON-ready series sized to a client-requested `downsample` target. FFTs are computed lazily, stored as `DerivedArtifact` rows + MinIO objects keyed by `(source_hash, params_hash)`. Frontend adds `AppShell` + sidebar nav, runs dashboard + run detail with a tabbed plot panel (Time / FFT) using `react-plotly.js`.

**Tech Stack:** Adds `scipy`, `numpy`, `h5py` (already in deps from Plan 1), `react-plotly.js` + `plotly.js` on the frontend.

---

## Conventions

- Paths relative to repo root `/home/tcollins/dev/prism`.
- Pytest/uv: `cd /home/tcollins/dev/prism/apps/api && uv run pytest -v`.
- npm/vitest: `cd /home/tcollins/dev/prism/apps/web && npm test`.
- TDD: failing test → impl → passing test → commit.
- Commits: Conventional Commits. **No `Co-Authored-By` lines.**
- Bash cwd may be pinned to a stub; always use absolute paths or explicit `cd`.

## Review items folded in from Plan 1

- **I5** — `AuthProvider` distinguishes transport errors from 401 (Task 8.1)
- **S7** — split `AuthContext` into its own module (Task 8.1)
- **Web Dockerfile uses `npm ci` with committed `package-lock.json`** (Task 0.1)

## Pre-flight (Phase 0): small review fixups

### Task 0.1: Web Dockerfile uses `npm ci`

**Files:**

- Modify: `apps/web/Dockerfile` (prod)
- Modify: `apps/web/Dockerfile.dev`

- [ ] **Step 1: Verify `package-lock.json` is committed**

```bash
ls /home/tcollins/dev/prism/apps/web/package-lock.json && cd /home/tcollins/dev/prism && git ls-files apps/web/package-lock.json
```

Both should return a path. If not, commit the lockfile first:

```bash
cd /home/tcollins/dev/prism && git add apps/web/package-lock.json && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "chore(web): commit package-lock.json"
```

- [ ] **Step 2: Update Dockerfiles to copy the lockfile and use `npm ci`**

`apps/web/Dockerfile`:

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
```

`apps/web/Dockerfile.dev`:

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
EXPOSE 5173
```

- [ ] **Step 3: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/web/Dockerfile apps/web/Dockerfile.dev && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "build(web): use npm ci + lockfile for reproducible image builds"
```

---

## Phase 1: Waveform parsers

### Task 1.1: `parsers/waveform.py`

**Files:**

- Create: `apps/api/src/prism_api/parsers/waveform.py`
- Create: `apps/api/tests/test_parsers_waveform.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_parsers_waveform.py`:

```python
"""Waveform loader tests: CSV, NPY, HDF5."""
import io

import h5py
import numpy as np
import pytest

from prism_api.models import ArtifactKind
from prism_api.parsers.waveform import load_waveform


def test_csv_single_column() -> None:
    data = b"0.0\n0.5\n-0.5\n"
    wf = load_waveform(ArtifactKind.WAVEFORM_CSV, data, filename="x.csv")
    assert np.allclose(wf.samples, [0.0, 0.5, -0.5])
    assert wf.sample_rate is None


def test_csv_with_header_and_sample_rate_inline() -> None:
    # Convention: a leading `# sample_rate=48000` comment is parsed as metadata
    data = b"# sample_rate=48000\n0.1\n0.2\n0.3\n"
    wf = load_waveform(ArtifactKind.WAVEFORM_CSV, data, filename="x.csv")
    assert wf.sample_rate == 48000
    assert np.allclose(wf.samples, [0.1, 0.2, 0.3])


def test_npy_load() -> None:
    buf = io.BytesIO()
    np.save(buf, np.array([0.1, 0.2, 0.3], dtype=np.float32))
    wf = load_waveform(ArtifactKind.WAVEFORM_NPY, buf.getvalue(), filename="x.npy")
    assert np.allclose(wf.samples, [0.1, 0.2, 0.3], atol=1e-7)


def test_hdf5_load_with_sample_rate_attr() -> None:
    buf = io.BytesIO()
    with h5py.File(buf, "w") as f:
        dset = f.create_dataset("waveform", data=np.array([0.0, 1.0, 2.0]))
        dset.attrs["sample_rate"] = 22050
    wf = load_waveform(ArtifactKind.WAVEFORM_HDF5, buf.getvalue(), filename="x.h5")
    assert np.allclose(wf.samples, [0.0, 1.0, 2.0])
    assert wf.sample_rate == 22050


def test_unsupported_kind_raises() -> None:
    with pytest.raises(ValueError):
        load_waveform(ArtifactKind.LOG_TEXT, b"hello", filename="x.log")
```

- [ ] **Step 2: Run test (FAIL)**

```bash
cd /home/tcollins/dev/prism/apps/api && uv run pytest tests/test_parsers_waveform.py -v
```

- [ ] **Step 3: Implement**

`apps/api/src/prism_api/parsers/waveform.py`:

```python
"""Waveform loaders for CSV, NPY, HDF5."""
from __future__ import annotations

import io
import re
from dataclasses import dataclass

import h5py
import numpy as np

from prism_api.models import ArtifactKind

_SAMPLE_RATE_RE = re.compile(r"^#\s*sample_rate\s*=\s*(\d+)\s*$", re.MULTILINE)


@dataclass
class Waveform:
    samples: np.ndarray  # 1-D float64
    sample_rate: int | None = None


def _load_csv(data: bytes) -> Waveform:
    text = data.decode("utf-8", errors="replace")
    match = _SAMPLE_RATE_RE.search(text)
    sample_rate = int(match.group(1)) if match else None
    # Strip comment lines and blank lines
    rows = [line for line in text.splitlines() if line and not line.lstrip().startswith("#")]
    values = np.fromstring(",".join(rows), sep=",", dtype=np.float64) if rows else np.empty(0)
    return Waveform(samples=values, sample_rate=sample_rate)


def _load_npy(data: bytes) -> Waveform:
    arr = np.load(io.BytesIO(data))
    return Waveform(samples=np.asarray(arr, dtype=np.float64))


def _load_hdf5(data: bytes) -> Waveform:
    with h5py.File(io.BytesIO(data), "r") as f:
        # Pick the first dataset in the file
        dataset_name = next(name for name in f if isinstance(f[name], h5py.Dataset))
        dset = f[dataset_name]
        samples = np.asarray(dset[...], dtype=np.float64)
        sample_rate = int(dset.attrs["sample_rate"]) if "sample_rate" in dset.attrs else None
    return Waveform(samples=samples, sample_rate=sample_rate)


def load_waveform(kind: ArtifactKind, data: bytes, *, filename: str) -> Waveform:
    """Load a waveform from its raw bytes based on artifact kind."""
    if kind == ArtifactKind.WAVEFORM_CSV:
        return _load_csv(data)
    if kind == ArtifactKind.WAVEFORM_NPY:
        return _load_npy(data)
    if kind == ArtifactKind.WAVEFORM_HDF5:
        return _load_hdf5(data)
    raise ValueError(f"{kind} is not a waveform kind")
```

- [ ] **Step 4: Run tests (PASS)**

- [ ] **Step 5: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(api): waveform loaders for CSV / NPY / HDF5"
```

---

## Phase 2: DSP — downsample + FFT

### Task 2.1: `dsp/downsample.py`

**Files:**

- Create: `apps/api/src/prism_api/dsp/__init__.py` (empty)
- Create: `apps/api/src/prism_api/dsp/downsample.py`
- Create: `apps/api/tests/test_dsp_downsample.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_dsp_downsample.py`:

```python
import numpy as np

from prism_api.dsp.downsample import downsample_for_plot


def test_pass_through_if_already_small() -> None:
    samples = np.arange(100, dtype=np.float64)
    got = downsample_for_plot(samples, target=500)
    assert np.array_equal(got.samples, samples)
    assert got.stride == 1


def test_decimates_to_roughly_target_size() -> None:
    samples = np.arange(10_000, dtype=np.float64)
    got = downsample_for_plot(samples, target=1_000)
    assert abs(len(got.samples) - 1_000) <= 10
    assert got.stride >= 10


def test_preserves_peaks_with_minmax_pair() -> None:
    # Generate a sine with fast spikes; min/max pairing should preserve extremes
    t = np.arange(10_000, dtype=np.float64)
    samples = np.sin(t / 100) + 0.1 * np.sin(t * 5)
    got = downsample_for_plot(samples, target=400)
    assert abs(got.samples.max() - samples.max()) < 0.05
    assert abs(got.samples.min() - samples.min()) < 0.05
```

- [ ] **Step 2: Run test (FAIL)**

- [ ] **Step 3: Implement**

`apps/api/src/prism_api/dsp/__init__.py`: empty.

`apps/api/src/prism_api/dsp/downsample.py`:

```python
"""Downsample a waveform for plotting — preserves min/max within each bucket."""
from dataclasses import dataclass

import numpy as np


@dataclass
class DownsampledSeries:
    samples: np.ndarray
    stride: int


def downsample_for_plot(samples: np.ndarray, *, target: int) -> DownsampledSeries:
    """Reduce `samples` to approximately `target` points using min/max pairing.

    Each output bucket contributes two points (min, then max) so fast transients
    stay visible. If the input already fits, it's returned unchanged.
    """
    n = len(samples)
    if n <= target:
        return DownsampledSeries(samples=samples, stride=1)

    # Two points per bucket -> bucket count ≈ target/2
    bucket_count = max(1, target // 2)
    stride = max(1, n // bucket_count)
    # Trim so samples divides evenly by stride
    end = (n // stride) * stride
    reshaped = samples[:end].reshape(-1, stride)
    mins = reshaped.min(axis=1)
    maxs = reshaped.max(axis=1)
    # Interleave (min, max) per bucket
    interleaved = np.empty(mins.size + maxs.size, dtype=samples.dtype)
    interleaved[0::2] = mins
    interleaved[1::2] = maxs
    return DownsampledSeries(samples=interleaved, stride=stride)
```

- [ ] **Step 4: Run tests (PASS)**

- [ ] **Step 5: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(api): dsp.downsample — min/max decimation for plotting"
```

---

### Task 2.2: `dsp/fft.py`

**Files:**

- Create: `apps/api/src/prism_api/dsp/fft.py`
- Create: `apps/api/tests/test_dsp_fft.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_dsp_fft.py`:

```python
import hashlib

import numpy as np

from prism_api.dsp.fft import FFTParams, compute_fft, params_hash


def test_params_hash_stable() -> None:
    p1 = FFTParams(window="hann", nfft=1024, overlap=0.5)
    p2 = FFTParams(window="hann", nfft=1024, overlap=0.5)
    assert params_hash(p1) == params_hash(p2)


def test_params_hash_differs() -> None:
    assert params_hash(FFTParams(window="hann", nfft=1024, overlap=0.5)) != params_hash(
        FFTParams(window="hamming", nfft=1024, overlap=0.5)
    )


def test_compute_fft_finds_dominant_bin() -> None:
    fs = 8000
    t = np.arange(4096) / fs
    signal = np.sin(2 * np.pi * 1000 * t).astype(np.float64)
    result = compute_fft(signal, sample_rate=fs, params=FFTParams(window="hann", nfft=1024, overlap=0.5))
    assert len(result.frequencies) == len(result.magnitudes)
    peak_idx = int(np.argmax(result.magnitudes))
    peak_freq = result.frequencies[peak_idx]
    assert abs(peak_freq - 1000) < 50


def test_compute_fft_without_sample_rate_uses_unit_hz() -> None:
    result = compute_fft(np.ones(512), sample_rate=None, params=FFTParams(window="hann", nfft=256, overlap=0.5))
    # Without a sample rate we fall back to fs=1.0; peak at f=0 for constant signal
    assert result.sample_rate == 1.0
    assert result.frequencies[0] == 0.0
```

- [ ] **Step 2: Run test (FAIL)**

- [ ] **Step 3: Implement**

`apps/api/src/prism_api/dsp/fft.py`:

```python
"""FFT via Welch's method with stable parameter hashing for derived-artifact caching."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
from scipy.signal import welch

Window = Literal["hann", "hamming", "boxcar"]


@dataclass(frozen=True)
class FFTParams:
    window: Window = "hann"
    nfft: int = 1024
    overlap: float = 0.5


@dataclass
class FFTResult:
    frequencies: np.ndarray
    magnitudes: np.ndarray
    sample_rate: float


def params_hash(p: FFTParams) -> str:
    """Stable hex digest for caching by FFT parameters."""
    payload = json.dumps(asdict(p), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def compute_fft(samples: np.ndarray, *, sample_rate: int | float | None, params: FFTParams) -> FFTResult:
    fs = float(sample_rate) if sample_rate else 1.0
    nperseg = min(params.nfft, len(samples))
    noverlap = int(nperseg * params.overlap)
    freqs, psd = welch(
        samples.astype(np.float64),
        fs=fs,
        window=params.window,
        nperseg=nperseg,
        noverlap=noverlap,
        scaling="spectrum",
    )
    # magnitudes: sqrt of spectrum (so it's |X(f)| rather than |X(f)|^2)
    magnitudes = np.sqrt(psd)
    return FFTResult(frequencies=freqs.astype(np.float64), magnitudes=magnitudes.astype(np.float64), sample_rate=fs)
```

- [ ] **Step 4: Run tests (PASS)**

- [ ] **Step 5: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(api): dsp.fft — Welch method with stable params_hash"
```

---

## Phase 3: Read endpoints

### Task 3.1: Run + case + artifact schemas

**Files:**

- Modify: `apps/api/src/prism_api/schemas/run.py` (add `RunDetail`, `RunListItem`)
- Create: `apps/api/src/prism_api/schemas/case.py` (CaseDetail)
- Create: `apps/api/src/prism_api/schemas/artifact.py` (ArtifactOut, WaveformResponse, FFTResponse)

- [ ] **Step 1: Update schemas**

Append to `apps/api/src/prism_api/schemas/run.py`:

```python
class SuiteSummary(BaseModel):
    id: str
    name: str
    pass_count: int
    fail_count: int
    error_count: int
    skip_count: int
    duration_ms: int


class RunDetail(RunOut):
    suites: list[SuiteSummary] = Field(default_factory=list)


class RunListItem(BaseModel):
    id: str
    project_id: str
    name: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    pass_count: int
    fail_count: int
    error_count: int
    skip_count: int
    tags: list[RunTagOut] = Field(default_factory=list)
```

`apps/api/src/prism_api/schemas/case.py`:

```python
from pydantic import BaseModel, Field


class CaseArtifactOut(BaseModel):
    id: str
    kind: str
    filename: str
    size_bytes: int


class CaseDetail(BaseModel):
    id: str
    suite_id: str
    classname: str
    name: str
    status: str
    duration_ms: int
    failure_message: str | None
    failure_trace: str | None
    artifacts: list[CaseArtifactOut] = Field(default_factory=list)
```

`apps/api/src/prism_api/schemas/artifact.py`:

```python
from pydantic import BaseModel


class ArtifactOut(BaseModel):
    id: str
    owner_type: str
    owner_id: str
    kind: str
    filename: str
    size_bytes: int
    content_hash: str


class WaveformResponse(BaseModel):
    samples: list[float]
    sample_rate: int | None
    stride: int
    total_samples: int


class FFTResponse(BaseModel):
    frequencies: list[float]
    magnitudes: list[float]
    sample_rate: float
    params: dict
```

- [ ] **Step 2: Commit (no test yet — these are used by the next tasks)**

```bash
cd /home/tcollins/dev/prism && git add apps/api/src/prism_api/schemas/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(api): add read schemas — RunDetail, RunListItem, CaseDetail, WaveformResponse, FFTResponse"
```

---

### Task 3.2: Runs read endpoints

**Files:**

- Modify: `apps/api/src/prism_api/routers/runs.py` (add GET endpoints + list filter)
- Modify: `apps/api/src/prism_api/repos/runs.py` (add `list_with_filters`, `aggregate_counts_by_run`)
- Create: `apps/api/tests/test_runs_read.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_runs_read.py`:

```python
import io
import json
import zipfile

from fastapi.testclient import TestClient


def _login(client: TestClient) -> None:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})


def _upload(client: TestClient, project_slug: str = "audio", name: str = "r") -> str:
    junit = b"""<?xml version="1.0"?><testsuites>
<testsuite name="dsp" tests="2" failures="1" time="0.1">
<testcase classname="codec" name="ok" time="0.05"/>
<testcase classname="codec" name="bad" time="0.05"><failure message="x">t</failure></testcase>
</testsuite></testsuites>"""
    arc = io.BytesIO()
    with zipfile.ZipFile(arc, "w") as zf:
        zf.writestr("dsp__ok__waveform.csv", "# sample_rate=48000\n0.1\n0.2\n0.3\n")
    resp = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", junit, "application/xml"), "archive": ("a.zip", arc.getvalue(), "application/zip")},
        data={"metadata": json.dumps({"project_slug": project_slug, "name": name, "tags": {"branch": "main"}})},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_list_runs_empty(client: TestClient, seed_admin, patch_ingest) -> None:
    _login(client)
    client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    resp = client.get("/api/v1/runs?project=audio")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_runs_basic(client: TestClient, seed_admin, patch_ingest) -> None:
    _login(client)
    client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    _upload(client, name="r1")
    _upload(client, name="r2")

    resp = client.get("/api/v1/runs?project=audio")
    assert resp.status_code == 200
    runs = resp.json()
    assert [r["name"] for r in runs] == ["r2", "r1"]  # newest first
    assert runs[0]["pass_count"] == 1
    assert runs[0]["fail_count"] == 1


def test_list_runs_filter_status(client: TestClient, seed_admin, patch_ingest) -> None:
    _login(client)
    client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    _upload(client, name="r-mixed")
    resp = client.get("/api/v1/runs?project=audio&status=mixed")
    assert len(resp.json()) == 1
    resp2 = client.get("/api/v1/runs?project=audio&status=pass")
    assert resp2.json() == []


def test_run_detail(client: TestClient, seed_admin, patch_ingest) -> None:
    _login(client)
    client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    run_id = _upload(client)
    resp = client.get(f"/api/v1/runs/{run_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["id"] == run_id
    assert {s["name"] for s in detail["suites"]} == {"dsp"}
    assert detail["suites"][0]["pass_count"] == 1


def test_run_detail_not_found(client: TestClient, seed_admin) -> None:
    _login(client)
    resp = client.get("/api/v1/runs/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test (FAIL)**

- [ ] **Step 3: Extend `RunRepo`**

Append to `apps/api/src/prism_api/repos/runs.py`:

```python
from sqlalchemy import func

from prism_api.models.suite import TestSuite


class RunRepo:
    # ... existing methods ...

    def list_with_filters(
        self,
        *,
        project_id: str,
        status: str | None = None,
        limit: int = 50,
    ) -> list[TestRun]:
        stmt = select(TestRun).where(TestRun.project_id == project_id)
        if status:
            stmt = stmt.where(TestRun.status == RunStatus(status))
        stmt = stmt.order_by(TestRun.created_at.desc()).limit(limit)
        return list(self._session.execute(stmt).scalars())

    def aggregate_counts_by_run(self, run_id: str) -> dict[str, int]:
        row = self._session.execute(
            select(
                func.coalesce(func.sum(TestSuite.pass_count), 0),
                func.coalesce(func.sum(TestSuite.fail_count), 0),
                func.coalesce(func.sum(TestSuite.error_count), 0),
                func.coalesce(func.sum(TestSuite.skip_count), 0),
            ).where(TestSuite.run_id == run_id)
        ).one()
        return {
            "pass_count": int(row[0]),
            "fail_count": int(row[1]),
            "error_count": int(row[2]),
            "skip_count": int(row[3]),
        }
```

(Important: the existing `RunRepo` was defined as one class; add these methods *inside* that class, not as a new class definition.)

- [ ] **Step 4: Add GET endpoints to runs router**

Replace the full `apps/api/src/prism_api/routers/runs.py` (add the imports for the new schemas):

```python
"""Run upload + read endpoints."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from prism_api.config import Settings
from prism_api.deps import current_user, get_settings_dep, session_dep
from prism_api.models.run import RunStatus
from prism_api.models.user import User
from prism_api.repos.projects import ProjectRepo
from prism_api.repos.runs import RunRepo
from prism_api.repos.suites import SuiteRepo
from prism_api.schemas.run import (
    CreateRunMetadata,
    RunDetail,
    RunListItem,
    RunOut,
    RunTagOut,
    SuiteSummary,
)
from prism_api.storage import ObjectStorage, build_storage
from prism_api.worker.tasks import run_ingest

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


def enqueue_ingest(
    run_id: str,
    junit_bytes: bytes,
    archive_bytes: bytes | None,
    storage: ObjectStorage,
) -> None:
    junit_key = storage.put_raw(junit_bytes, filename="junit.xml")
    archive_key = storage.put_raw(archive_bytes, filename="archive.zip") if archive_bytes else None
    run_ingest.delay(run_id, junit_key, archive_key)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=RunOut)
async def upload_run(
    junit: UploadFile = File(...),
    metadata: str = Form(...),
    archive: UploadFile | None = File(default=None),
    current: User = Depends(current_user),
    settings: Settings = Depends(get_settings_dep),
    session: Session = Depends(session_dep),
) -> RunOut:
    try:
        meta = CreateRunMetadata.model_validate(json.loads(metadata))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"invalid metadata: {exc}") from exc

    project = ProjectRepo(session).get_by_slug(meta.project_slug)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"project '{meta.project_slug}' not found")

    runs = RunRepo(session)
    run = runs.create(project_id=project.id, name=meta.name, status=RunStatus.PENDING, created_by=current.id)
    for k, v in meta.tags.items():
        runs.add_tag(run.id, k, v)
    session.flush()

    junit_bytes = await junit.read()
    archive_bytes = await archive.read() if archive is not None else None

    storage = build_storage(settings)
    storage.ensure_bucket()
    enqueue_ingest(run.id, junit_bytes, archive_bytes, storage)

    session.refresh(run)
    tags = runs.tags_for(run.id)
    return RunOut(
        id=run.id, project_id=run.project_id, name=run.name, status=run.status.value,
        started_at=run.started_at, finished_at=run.finished_at,
        junit_artifact_id=run.junit_artifact_id,
        tags=[RunTagOut(key=t.key, value=t.value) for t in tags],
    )


@router.get("", response_model=list[RunListItem])
def list_runs(
    project: str = Query(..., description="Project slug"),
    status_: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[RunListItem]:
    proj = ProjectRepo(session).get_by_slug(project)
    if proj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"project '{project}' not found")
    runs = RunRepo(session)
    items = runs.list_with_filters(project_id=proj.id, status=status_, limit=limit)
    result: list[RunListItem] = []
    for r in items:
        counts = runs.aggregate_counts_by_run(r.id)
        tags = runs.tags_for(r.id)
        result.append(RunListItem(
            id=r.id, project_id=r.project_id, name=r.name, status=r.status.value,
            started_at=r.started_at, finished_at=r.finished_at,
            tags=[RunTagOut(key=t.key, value=t.value) for t in tags],
            **counts,
        ))
    return result


@router.get("/{run_id}", response_model=RunDetail)
def get_run(
    run_id: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> RunDetail:
    runs = RunRepo(session)
    run = runs.get_by_id(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    suites = [
        SuiteSummary(
            id=s.id, name=s.name, pass_count=s.pass_count, fail_count=s.fail_count,
            error_count=s.error_count, skip_count=s.skip_count, duration_ms=s.duration_ms,
        )
        for s in SuiteRepo(session).list_by_run(run.id)
    ]
    tags = [RunTagOut(key=t.key, value=t.value) for t in runs.tags_for(run.id)]
    return RunDetail(
        id=run.id, project_id=run.project_id, name=run.name, status=run.status.value,
        started_at=run.started_at, finished_at=run.finished_at,
        junit_artifact_id=run.junit_artifact_id, tags=tags, suites=suites,
    )
```

- [ ] **Step 5: Run tests (PASS)**

- [ ] **Step 6: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(api): GET /runs list + GET /runs/:id detail with aggregated counts"
```

---

### Task 3.3: Cases + suites read endpoints

**Files:**

- Create: `apps/api/src/prism_api/routers/cases.py`
- Create: `apps/api/src/prism_api/routers/suites.py`
- Modify: `apps/api/src/prism_api/main.py` (include both routers)
- Create: `apps/api/tests/test_cases_router.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_cases_router.py`:

```python
import io
import json
import zipfile

from fastapi.testclient import TestClient


def _login(client: TestClient) -> None:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})


def _bootstrap(client: TestClient) -> str:
    client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    junit = b"""<?xml version="1.0"?><testsuites>
<testsuite name="dsp" tests="1" failures="0" time="0.1">
<testcase classname="codec" name="ok" time="0.05"/>
</testsuite></testsuites>"""
    arc = io.BytesIO()
    with zipfile.ZipFile(arc, "w") as zf:
        zf.writestr("dsp__ok__waveform.csv", "# sample_rate=48000\n0.1\n0.2\n")
    resp = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", junit, "application/xml"), "archive": ("a.zip", arc.getvalue(), "application/zip")},
        data={"metadata": json.dumps({"project_slug": "audio", "name": "r1"})},
    )
    return resp.json()["id"]


def test_suite_cases_list(client: TestClient, seed_admin, patch_ingest) -> None:
    _login(client)
    run_id = _bootstrap(client)
    detail = client.get(f"/api/v1/runs/{run_id}").json()
    suite_id = detail["suites"][0]["id"]
    cases = client.get(f"/api/v1/suites/{suite_id}/cases").json()
    assert [c["name"] for c in cases] == ["ok"]


def test_case_detail(client: TestClient, seed_admin, patch_ingest) -> None:
    _login(client)
    run_id = _bootstrap(client)
    detail = client.get(f"/api/v1/runs/{run_id}").json()
    suite_id = detail["suites"][0]["id"]
    cases = client.get(f"/api/v1/suites/{suite_id}/cases").json()
    case_id = cases[0]["id"]

    resp = client.get(f"/api/v1/cases/{case_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "ok"
    # The attached waveform CSV should be in artifacts
    assert any(a["kind"] == "waveform_csv" for a in body["artifacts"])


def test_case_not_found(client: TestClient, seed_admin) -> None:
    _login(client)
    resp = client.get("/api/v1/cases/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test (FAIL)**

- [ ] **Step 3: Implement suites router**

`apps/api/src/prism_api/routers/suites.py`:

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from prism_api.deps import current_user, session_dep
from prism_api.models.user import User
from prism_api.repos.suites import CaseRepo


class CaseListItem(BaseModel):
    id: str
    classname: str
    name: str
    status: str
    duration_ms: int


router = APIRouter(prefix="/api/v1/suites", tags=["suites"])


@router.get("/{suite_id}/cases", response_model=list[CaseListItem])
def list_cases(
    suite_id: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[CaseListItem]:
    return [
        CaseListItem(id=c.id, classname=c.classname, name=c.name, status=c.status.value, duration_ms=c.duration_ms)
        for c in CaseRepo(session).list_by_suite(suite_id)
    ]
```

- [ ] **Step 4: Implement cases router**

`apps/api/src/prism_api/routers/cases.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from prism_api.deps import current_user, session_dep
from prism_api.models.user import User
from prism_api.repos.artifacts import ArtifactRepo
from prism_api.repos.suites import CaseRepo
from prism_api.schemas.case import CaseArtifactOut, CaseDetail

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])


@router.get("/{case_id}", response_model=CaseDetail)
def get_case(
    case_id: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> CaseDetail:
    # CaseRepo doesn't have get_by_id — fetch directly
    from prism_api.models.suite import TestCase
    case = session.get(TestCase, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case not found")
    artifacts = [
        CaseArtifactOut(id=a.id, kind=a.kind.value, filename=a.filename, size_bytes=a.size_bytes)
        for a in ArtifactRepo(session).list_by_owner("case", case.id)
    ]
    return CaseDetail(
        id=case.id, suite_id=case.suite_id, classname=case.classname, name=case.name,
        status=case.status.value, duration_ms=case.duration_ms,
        failure_message=case.failure_message, failure_trace=case.failure_trace,
        artifacts=artifacts,
    )
```

- [ ] **Step 5: Wire both routers in main.py**

```python
from prism_api.routers import cases as cases_router
from prism_api.routers import suites as suites_router
...
app.include_router(suites_router.router)
app.include_router(cases_router.router)
```

- [ ] **Step 6: Run tests (PASS)**

- [ ] **Step 7: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(api): GET /suites/:id/cases and GET /cases/:id"
```

---

### Task 3.4: Artifacts router (download + waveform + FFT)

**Files:**

- Create: `apps/api/src/prism_api/routers/artifacts.py`
- Modify: `apps/api/src/prism_api/main.py` (include artifacts router)
- Create: `apps/api/tests/test_artifacts_router.py`

- [ ] **Step 1: Write the failing test**

`apps/api/tests/test_artifacts_router.py`:

```python
import io
import json
import zipfile

import numpy as np
from fastapi.testclient import TestClient


def _login(client: TestClient) -> None:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})


def _bootstrap_with_waveform(client: TestClient) -> str:
    client.post("/api/v1/projects", json={"slug": "audio", "name": "Audio"})
    junit = b"""<?xml version="1.0"?><testsuites>
<testsuite name="dsp" tests="1" failures="0" time="0.1">
<testcase classname="c" name="ok" time="0.05"/>
</testsuite></testsuites>"""
    # 1kHz sine at fs=8kHz, 2048 samples
    fs = 8000
    t = np.arange(2048) / fs
    samples = np.sin(2 * np.pi * 1000 * t)
    csv = f"# sample_rate={fs}\n" + "\n".join(str(x) for x in samples) + "\n"
    arc = io.BytesIO()
    with zipfile.ZipFile(arc, "w") as zf:
        zf.writestr("dsp__ok__wave.csv", csv)
    resp = client.post(
        "/api/v1/runs",
        files={"junit": ("j.xml", junit, "application/xml"), "archive": ("a.zip", arc.getvalue(), "application/zip")},
        data={"metadata": json.dumps({"project_slug": "audio", "name": "r1"})},
    )
    run_id = resp.json()["id"]
    # Find the waveform artifact
    suites = client.get(f"/api/v1/runs/{run_id}").json()["suites"]
    cases = client.get(f"/api/v1/suites/{suites[0]['id']}/cases").json()
    case = client.get(f"/api/v1/cases/{cases[0]['id']}").json()
    waveform = next(a for a in case["artifacts"] if a["kind"] == "waveform_csv")
    return waveform["id"]


def test_artifact_metadata(client: TestClient, seed_admin, patch_ingest) -> None:
    _login(client)
    art_id = _bootstrap_with_waveform(client)
    resp = client.get(f"/api/v1/artifacts/{art_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "waveform_csv"
    assert body["filename"].endswith("wave.csv")


def test_artifact_waveform_endpoint(client: TestClient, seed_admin, patch_ingest) -> None:
    _login(client)
    art_id = _bootstrap_with_waveform(client)
    resp = client.get(f"/api/v1/artifacts/{art_id}/waveform?downsample=400")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sample_rate"] == 8000
    assert body["total_samples"] == 2048
    assert 200 <= len(body["samples"]) <= 450  # downsampled


def test_artifact_fft_endpoint(client: TestClient, seed_admin, patch_ingest) -> None:
    _login(client)
    art_id = _bootstrap_with_waveform(client)
    resp = client.get(f"/api/v1/artifacts/{art_id}/fft?window=hann&nfft=1024&overlap=0.5")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["frequencies"]) == len(body["magnitudes"])
    # peak should land near 1000 Hz
    freqs = body["frequencies"]
    mags = body["magnitudes"]
    peak_idx = max(range(len(mags)), key=lambda i: mags[i])
    assert abs(freqs[peak_idx] - 1000) < 50


def test_artifact_fft_cached_second_call(client: TestClient, seed_admin, patch_ingest) -> None:
    _login(client)
    art_id = _bootstrap_with_waveform(client)
    r1 = client.get(f"/api/v1/artifacts/{art_id}/fft?window=hann&nfft=1024&overlap=0.5")
    assert r1.status_code == 200
    r2 = client.get(f"/api/v1/artifacts/{art_id}/fft?window=hann&nfft=1024&overlap=0.5")
    assert r2.status_code == 200
    assert r1.json()["frequencies"] == r2.json()["frequencies"]
```

- [ ] **Step 2: Run test (FAIL)**

- [ ] **Step 3: Implement artifacts router**

`apps/api/src/prism_api/routers/artifacts.py`:

```python
"""Artifact endpoints: metadata, download, waveform JSON, FFT JSON."""
from __future__ import annotations

import io

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from prism_api.config import Settings
from prism_api.deps import current_user, get_settings_dep, session_dep
from prism_api.dsp.downsample import downsample_for_plot
from prism_api.dsp.fft import FFTParams, compute_fft, params_hash
from prism_api.models import ArtifactKind, DerivedKind
from prism_api.models.user import User
from prism_api.parsers.waveform import load_waveform
from prism_api.repos.artifacts import ArtifactRepo, DerivedRepo
from prism_api.schemas.artifact import ArtifactOut, FFTResponse, WaveformResponse
from prism_api.storage import build_storage

router = APIRouter(prefix="/api/v1/artifacts", tags=["artifacts"])

_WAVEFORM_KINDS = {ArtifactKind.WAVEFORM_CSV, ArtifactKind.WAVEFORM_NPY, ArtifactKind.WAVEFORM_HDF5}


def _fetch_artifact_or_404(session: Session, artifact_id: str):
    a = ArtifactRepo(session).get_by_id(artifact_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "artifact not found")
    return a


@router.get("/{artifact_id}", response_model=ArtifactOut)
def get_artifact(
    artifact_id: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> ArtifactOut:
    a = _fetch_artifact_or_404(session, artifact_id)
    return ArtifactOut(
        id=a.id, owner_type=a.owner_type, owner_id=a.owner_id, kind=a.kind.value,
        filename=a.filename, size_bytes=a.size_bytes, content_hash=a.content_hash,
    )


@router.get("/{artifact_id}/download")
def download_artifact(
    artifact_id: str,
    _: User = Depends(current_user),
    settings: Settings = Depends(get_settings_dep),
    session: Session = Depends(session_dep),
) -> RedirectResponse:
    a = _fetch_artifact_or_404(session, artifact_id)
    storage = build_storage(settings)
    url = storage.presigned_url(a.storage_key, expires_in=300)
    return RedirectResponse(url, status_code=307)


@router.get("/{artifact_id}/waveform", response_model=WaveformResponse)
def get_waveform(
    artifact_id: str,
    downsample: int = Query(default=2000, ge=100, le=50_000),
    _: User = Depends(current_user),
    settings: Settings = Depends(get_settings_dep),
    session: Session = Depends(session_dep),
) -> WaveformResponse:
    a = _fetch_artifact_or_404(session, artifact_id)
    if a.kind not in _WAVEFORM_KINDS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"artifact kind {a.kind.value} is not a waveform")
    storage = build_storage(settings)
    data = storage.get_bytes(a.storage_key)
    wf = load_waveform(a.kind, data, filename=a.filename)
    ds = downsample_for_plot(wf.samples, target=downsample)
    return WaveformResponse(
        samples=ds.samples.tolist(),
        sample_rate=wf.sample_rate,
        stride=ds.stride,
        total_samples=int(wf.samples.size),
    )


@router.get("/{artifact_id}/fft", response_model=FFTResponse)
def get_fft(
    artifact_id: str,
    window: str = Query(default="hann"),
    nfft: int = Query(default=1024, ge=64, le=65536),
    overlap: float = Query(default=0.5, ge=0.0, le=0.9),
    _: User = Depends(current_user),
    settings: Settings = Depends(get_settings_dep),
    session: Session = Depends(session_dep),
) -> FFTResponse:
    a = _fetch_artifact_or_404(session, artifact_id)
    if a.kind not in _WAVEFORM_KINDS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"artifact kind {a.kind.value} is not a waveform")
    params = FFTParams(window=window, nfft=nfft, overlap=overlap)  # type: ignore[arg-type]
    ph = params_hash(params)
    storage = build_storage(settings)
    derived_repo = DerivedRepo(session)
    cached = derived_repo.find(source_artifact_id=a.id, kind=DerivedKind.FFT, params_hash=ph)
    if cached is not None:
        payload = storage.get_bytes(cached.storage_key)
        loaded = np.load(io.BytesIO(payload), allow_pickle=False)
        freqs, mags = loaded["freqs"], loaded["mags"]
        sample_rate = float(loaded["fs"][0])
    else:
        raw = storage.get_bytes(a.storage_key)
        wf = load_waveform(a.kind, raw, filename=a.filename)
        result = compute_fft(wf.samples, sample_rate=wf.sample_rate, params=params)
        freqs, mags, sample_rate = result.frequencies, result.magnitudes, result.sample_rate
        # Cache to MinIO
        buf = io.BytesIO()
        np.savez_compressed(buf, freqs=freqs, mags=mags, fs=np.array([sample_rate]))
        key = f"derived/fft/{a.content_hash}-{ph}.npz"
        storage.put_at(key, buf.getvalue(), content_type="application/octet-stream")
        derived_repo.create(source_artifact_id=a.id, kind=DerivedKind.FFT, storage_key=key, params_hash=ph)
        session.commit()
    return FFTResponse(
        frequencies=[float(x) for x in freqs],
        magnitudes=[float(x) for x in mags],
        sample_rate=float(sample_rate),
        params={"window": window, "nfft": nfft, "overlap": overlap},
    )
```

- [ ] **Step 4: Wire into main.py**

```python
from prism_api.routers import artifacts as artifacts_router
...
app.include_router(artifacts_router.router)
```

- [ ] **Step 5: Run tests (PASS)**

- [ ] **Step 6: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/api/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(api): artifact endpoints — metadata, download, waveform JSON, FFT (cached)"
```

---

## Phase 4: Frontend API types + query hooks

### Task 4.1: API types and query hooks

**Files:**

- Modify: `apps/web/src/api/types.ts` (add Run / Case / Artifact / Waveform / FFT types)
- Create: `apps/web/src/api/queries.ts` (TanStack Query hooks)

- [ ] **Step 1: Expand types**

Append to `apps/web/src/api/types.ts`:

```ts
export type RunStatus = 'pending' | 'pass' | 'fail' | 'mixed' | 'error';

export interface RunTag {
  key: string;
  value: string;
}

export interface RunListItem {
  id: string;
  project_id: string;
  name: string;
  status: RunStatus;
  started_at: string | null;
  finished_at: string | null;
  pass_count: number;
  fail_count: number;
  error_count: number;
  skip_count: number;
  tags: RunTag[];
}

export interface SuiteSummary {
  id: string;
  name: string;
  pass_count: number;
  fail_count: number;
  error_count: number;
  skip_count: number;
  duration_ms: number;
}

export interface RunDetail {
  id: string;
  project_id: string;
  name: string;
  status: RunStatus;
  started_at: string | null;
  finished_at: string | null;
  junit_artifact_id: string | null;
  tags: RunTag[];
  suites: SuiteSummary[];
}

export type CaseStatus = 'pass' | 'fail' | 'error' | 'skip';

export interface CaseListItem {
  id: string;
  classname: string;
  name: string;
  status: CaseStatus;
  duration_ms: number;
}

export interface CaseArtifact {
  id: string;
  kind: string;
  filename: string;
  size_bytes: number;
}

export interface CaseDetail {
  id: string;
  suite_id: string;
  classname: string;
  name: string;
  status: CaseStatus;
  duration_ms: number;
  failure_message: string | null;
  failure_trace: string | null;
  artifacts: CaseArtifact[];
}

export interface WaveformResponse {
  samples: number[];
  sample_rate: number | null;
  stride: number;
  total_samples: number;
}

export interface FFTResponse {
  frequencies: number[];
  magnitudes: number[];
  sample_rate: number;
  params: { window: string; nfft: number; overlap: number };
}
```

- [ ] **Step 2: Create query hooks**

`apps/web/src/api/queries.ts`:

```ts
import { useQuery } from '@tanstack/react-query';

import { api } from './client';
import type {
  CaseDetail,
  CaseListItem,
  FFTResponse,
  Project,
  RunDetail,
  RunListItem,
  WaveformResponse,
} from './types';

export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: async () => (await api.get<Project[]>('/projects')).data,
  });
}

export function useRuns(projectSlug: string | undefined, status?: string) {
  return useQuery({
    queryKey: ['runs', projectSlug, status ?? null],
    queryFn: async () => {
      const params: Record<string, string> = { project: projectSlug! };
      if (status) params.status = status;
      return (await api.get<RunListItem[]>('/runs', { params })).data;
    },
    enabled: Boolean(projectSlug),
  });
}

export function useRun(runId: string | undefined) {
  return useQuery({
    queryKey: ['runs', 'detail', runId],
    queryFn: async () => (await api.get<RunDetail>(`/runs/${runId}`)).data,
    enabled: Boolean(runId),
  });
}

export function useSuiteCases(suiteId: string | undefined) {
  return useQuery({
    queryKey: ['suites', suiteId, 'cases'],
    queryFn: async () => (await api.get<CaseListItem[]>(`/suites/${suiteId}/cases`)).data,
    enabled: Boolean(suiteId),
  });
}

export function useCase(caseId: string | undefined) {
  return useQuery({
    queryKey: ['cases', caseId],
    queryFn: async () => (await api.get<CaseDetail>(`/cases/${caseId}`)).data,
    enabled: Boolean(caseId),
  });
}

export function useWaveform(artifactId: string | undefined, downsample = 2000) {
  return useQuery({
    queryKey: ['artifacts', artifactId, 'waveform', downsample],
    queryFn: async () =>
      (await api.get<WaveformResponse>(`/artifacts/${artifactId}/waveform`, { params: { downsample } })).data,
    enabled: Boolean(artifactId),
  });
}

export function useFFT(
  artifactId: string | undefined,
  params: { window: string; nfft: number; overlap: number } = { window: 'hann', nfft: 1024, overlap: 0.5 },
) {
  return useQuery({
    queryKey: ['artifacts', artifactId, 'fft', params],
    queryFn: async () =>
      (await api.get<FFTResponse>(`/artifacts/${artifactId}/fft`, { params })).data,
    enabled: Boolean(artifactId),
  });
}
```

- [ ] **Step 3: Commit (no test; hooks are exercised via components in later tasks)**

```bash
cd /home/tcollins/dev/prism && git add apps/web/src/api/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(web): extended API types + TanStack Query hooks"
```

---

## Phase 5: App shell + AuthContext split + error discrimination

### Task 5.1: AuthContext split and error handling (I5 + S7)

**Files:**

- Create: `apps/web/src/auth/AuthContext.ts` (just the context + types)
- Modify: `apps/web/src/auth/AuthProvider.tsx` (use imported context, discriminate errors)
- Modify: `apps/web/src/auth/useAuth.ts` (import from AuthContext.ts)
- Modify: `apps/web/tests/AuthProvider.test.tsx` (add error-discrimination test)

- [ ] **Step 1: Create `AuthContext.ts`**

`apps/web/src/auth/AuthContext.ts`:

```ts
import { createContext } from 'react';

import type { User } from '../api/types';

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous' | 'unreachable';

export interface AuthContextValue {
  user: User | null;
  status: AuthStatus;
  refresh: () => Promise<unknown>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
```

- [ ] **Step 2: Update `AuthProvider.tsx` to discriminate errors**

`apps/web/src/auth/AuthProvider.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { type ReactNode } from 'react';

import { api } from '../api/client';
import type { User } from '../api/types';
import { AuthContext, type AuthStatus } from './AuthContext';

export function AuthProvider({ children }: { children: ReactNode }) {
  const query = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: async () => {
      const res = await api.get<User>('/auth/me');
      return res.data;
    },
    retry: false,
    staleTime: 60_000,
  });

  let status: AuthStatus;
  if (query.isLoading) {
    status = 'loading';
  } else if (query.data) {
    status = 'authenticated';
  } else if (axios.isAxiosError(query.error) && query.error.response?.status === 401) {
    status = 'anonymous';
  } else if (query.error) {
    status = 'unreachable';
  } else {
    status = 'anonymous';
  }

  return (
    <AuthContext.Provider value={{ user: query.data ?? null, status, refresh: query.refetch }}>
      {children}
    </AuthContext.Provider>
  );
}
```

- [ ] **Step 3: Update `useAuth.ts`**

```ts
import { useContext } from 'react';

import { AuthContext, type AuthContextValue } from './AuthContext';

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
```

- [ ] **Step 4: Update AuthProvider test to cover the new `unreachable` state**

The existing test asserts `'authenticated'` status after mount. Add one more test that simulates a 500 response and expects `status === 'unreachable'`. Refer to the existing `AuthProvider.test.tsx` for the mocking pattern (using `vi.hoisted` to mock `../src/api/client`). For the new test, override `api.get` to reject with an `AxiosError` with `response: { status: 500 }`:

```tsx
it('sets status to unreachable on transport error', async () => {
  // Update the mock for this test to return an AxiosError with 500 status
  const { AxiosError } = await import('axios');
  const err = new AxiosError('Server error');
  err.response = { status: 500, data: null, headers: {}, statusText: 'err', config: {} as any };
  mockedApi.get.mockRejectedValueOnce(err);

  const qc = new QueryClient();
  render(/* same providers */);
  await waitFor(() => {
    expect(screen.getByTestId('status').textContent).toBe('unreachable');
  });
});
```

Implement whatever test approach works with the existing `vi.hoisted` mock pattern. The goal is: 500 → `unreachable`, 401 → `anonymous`, 200 → `authenticated`.

- [ ] **Step 5: Run tests**

```bash
cd /home/tcollins/dev/prism/apps/web && npm test
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/web/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(web): AuthProvider discriminates 401 vs transport errors; split AuthContext (I5+S7)"
```

---

### Task 5.2: AppShell + Sidebar + TopBar

**Files:**

- Create: `apps/web/src/components/AppShell.tsx`
- Create: `apps/web/src/components/Sidebar.tsx`
- Create: `apps/web/src/components/TopBar.tsx`

- [ ] **Step 1: Implement the shell**

`apps/web/src/components/AppShell.tsx`:

```tsx
import { Box, Flex } from '@chakra-ui/react';
import type { ReactNode } from 'react';

import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <Flex minH="100vh">
      <Sidebar />
      <Box flex="1" display="flex" flexDirection="column">
        <TopBar />
        <Box as="main" flex="1" p={6} overflowY="auto">
          {children}
        </Box>
      </Box>
    </Flex>
  );
}
```

`apps/web/src/components/Sidebar.tsx`:

```tsx
import { Box, Heading, Stack, Text } from '@chakra-ui/react';
import { NavLink } from 'react-router-dom';

const navItems = [
  { to: '/', label: 'Runs' },
  { to: '/projects', label: 'Projects' },
];

export function Sidebar() {
  return (
    <Box
      as="nav"
      w="220px"
      bg="#171923"
      borderRightWidth={1}
      borderRightColor="#2d3748"
      px={4}
      py={5}
    >
      <Heading size="md" color="#63b3ed" mb={6} letterSpacing="tight">
        Prism
      </Heading>
      <Stack gap={1}>
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            style={({ isActive }) => ({
              display: 'block',
              padding: '6px 10px',
              borderRadius: '6px',
              fontSize: '13px',
              color: isActive ? '#fff' : '#a0aec0',
              background: isActive ? '#2d3748' : 'transparent',
              textDecoration: 'none',
            })}
          >
            {item.label}
          </NavLink>
        ))}
      </Stack>
      <Text mt={8} fontSize="xs" color="#4a5568" textTransform="uppercase">
        v0.2
      </Text>
    </Box>
  );
}
```

`apps/web/src/components/TopBar.tsx`:

```tsx
import { Box, Button, Flex, Text } from '@chakra-ui/react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

import { api } from '../api/client';
import { useAuth } from '../auth/useAuth';

export function TopBar() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    try {
      await api.post('/auth/logout');
    } catch (e) {
      if (!axios.isAxiosError(e)) throw e;
    }
    await refresh();
    navigate('/login');
  }

  return (
    <Flex
      as="header"
      h="56px"
      borderBottomWidth={1}
      borderBottomColor="#2d3748"
      px={6}
      alignItems="center"
      justifyContent="space-between"
    >
      <Box />
      <Flex alignItems="center" gap={3}>
        <Text fontSize="sm" color="#a0aec0">
          {user?.email ?? 'guest'}
        </Text>
        <Button size="sm" variant="outline" onClick={handleLogout}>
          Sign out
        </Button>
      </Flex>
    </Flex>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/web/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(web): AppShell / Sidebar / TopBar components"
```

---

## Phase 6: Dashboard (runs list)

### Task 6.1: RunsTable + ProjectDashboardPage + routing

**Files:**

- Create: `apps/web/src/components/RunsTable.tsx`
- Create: `apps/web/src/pages/ProjectDashboardPage.tsx`
- Modify: `apps/web/src/App.tsx` (routes: `/projects/:slug` → ProjectDashboardPage)
- Modify: `apps/web/src/pages/ProjectsPage.tsx` (wrap in AppShell, link rows to dashboard)

- [ ] **Step 1: Implement RunsTable**

`apps/web/src/components/RunsTable.tsx`:

```tsx
import { Box, Table, Text } from '@chakra-ui/react';
import { Link } from 'react-router-dom';

import type { RunListItem } from '../api/types';

const STATUS_COLOR: Record<string, string> = {
  pass: '#48bb78',
  fail: '#f56565',
  mixed: '#ed8936',
  error: '#f56565',
  pending: '#a0aec0',
};

function statusDot(status: string) {
  return (
    <Box
      display="inline-block"
      w="8px"
      h="8px"
      borderRadius="50%"
      bg={STATUS_COLOR[status] ?? '#a0aec0'}
      mr={2}
    />
  );
}

export function RunsTable({ runs }: { runs: RunListItem[] }) {
  if (runs.length === 0) {
    return <Text color="gray.500">No runs yet.</Text>;
  }
  return (
    <Table.Root variant="outline" size="sm">
      <Table.Header>
        <Table.Row>
          <Table.ColumnHeader>Status</Table.ColumnHeader>
          <Table.ColumnHeader>Run</Table.ColumnHeader>
          <Table.ColumnHeader>Pass</Table.ColumnHeader>
          <Table.ColumnHeader>Fail</Table.ColumnHeader>
          <Table.ColumnHeader>Tags</Table.ColumnHeader>
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {runs.map((r) => (
          <Table.Row key={r.id}>
            <Table.Cell>
              {statusDot(r.status)}
              {r.status}
            </Table.Cell>
            <Table.Cell>
              <Link to={`/runs/${r.id}`} style={{ color: '#63b3ed' }}>
                {r.name}
              </Link>
            </Table.Cell>
            <Table.Cell>{r.pass_count}</Table.Cell>
            <Table.Cell>{r.fail_count}</Table.Cell>
            <Table.Cell>
              {r.tags.map((t) => (
                <Text as="span" key={`${t.key}:${t.value}`} mr={2} fontFamily="mono" fontSize="xs">
                  {t.key}={t.value}
                </Text>
              ))}
            </Table.Cell>
          </Table.Row>
        ))}
      </Table.Body>
    </Table.Root>
  );
}
```

- [ ] **Step 2: Implement ProjectDashboardPage**

`apps/web/src/pages/ProjectDashboardPage.tsx`:

```tsx
import { Box, Heading, Text } from '@chakra-ui/react';
import { useParams } from 'react-router-dom';

import { useRuns } from '../api/queries';
import { AppShell } from '../components/AppShell';
import { RunsTable } from '../components/RunsTable';

export function ProjectDashboardPage() {
  const { slug } = useParams<{ slug: string }>();
  const runsQuery = useRuns(slug);

  return (
    <AppShell>
      <Heading size="lg" mb={4}>
        {slug}
      </Heading>
      {runsQuery.isLoading && <Text>Loading…</Text>}
      {runsQuery.isError && (
        <Text color="red.400">Could not load runs — {String(runsQuery.error)}</Text>
      )}
      {runsQuery.data && (
        <Box>
          <RunsTable runs={runsQuery.data} />
        </Box>
      )}
    </AppShell>
  );
}
```

- [ ] **Step 3: Update ProjectsPage to wrap in AppShell and link rows**

Re-render the existing table cells: each row's `slug` should link to `/projects/:slug`. Wrap the whole page's JSX return in `<AppShell>...</AppShell>`. Keep the creation form.

Key change in `apps/web/src/pages/ProjectsPage.tsx`:

```tsx
import { Link } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
// ...

// In the table body, wrap the slug cell:
<Table.Cell>
  <Link to={`/projects/${p.slug}`} style={{ color: '#63b3ed' }}>{p.slug}</Link>
</Table.Cell>

// Wrap the whole return:
return (
  <AppShell>
    ...existing heading + form + table...
  </AppShell>
);
```

- [ ] **Step 4: Add the dashboard route in `App.tsx`**

```tsx
import { ProjectDashboardPage } from './pages/ProjectDashboardPage';
// ...
<Route path="/projects/:slug" element={<ProtectedRoute><ProjectDashboardPage /></ProtectedRoute>} />
```

- [ ] **Step 5: Run tests (may need to update `App.test.tsx` if the redirect path changed)**

```bash
cd /home/tcollins/dev/prism/apps/web && npm test
```

- [ ] **Step 6: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/web/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(web): project dashboard with runs table"
```

---

## Phase 7: Run detail + plots

### Task 7.1: WaveformPlot + FFTPlot components

**Files:**

- Create: `apps/web/src/components/WaveformPlot.tsx`
- Create: `apps/web/src/components/FFTPlot.tsx`

First, add plotly deps:

- [ ] **Step 1: Install plotly**

```bash
cd /home/tcollins/dev/prism/apps/web && npm install plotly.js-basic-dist react-plotly.js @types/react-plotly.js
```

(Use `plotly.js-basic-dist` — smaller bundle than full plotly.js, sufficient for line charts.)

- [ ] **Step 2: Implement WaveformPlot**

`apps/web/src/components/WaveformPlot.tsx`:

```tsx
import { Box, Text } from '@chakra-ui/react';
import createPlotlyComponent from 'react-plotly.js/factory';
import Plotly from 'plotly.js-basic-dist';

import { useWaveform } from '../api/queries';

const Plot = createPlotlyComponent(Plotly);

export function WaveformPlot({ artifactId }: { artifactId: string }) {
  const q = useWaveform(artifactId, 4000);
  if (q.isLoading) return <Text>Loading waveform…</Text>;
  if (q.isError || !q.data) return <Text color="red.400">Failed to load waveform</Text>;
  const { samples, sample_rate, stride, total_samples } = q.data;
  const x = sample_rate
    ? samples.map((_, i) => ((i * stride) / sample_rate))
    : samples.map((_, i) => i * stride);
  const xTitle = sample_rate ? 'Time (s)' : 'Sample index';
  return (
    <Box>
      <Plot
        data={[{ x, y: samples, type: 'scatter', mode: 'lines', line: { color: '#63b3ed', width: 1 } }]}
        layout={{
          paper_bgcolor: '#171923',
          plot_bgcolor: '#0a0e13',
          font: { color: '#e2e8f0' },
          margin: { l: 50, r: 20, t: 20, b: 40 },
          xaxis: { title: { text: xTitle }, gridcolor: '#2d3748' },
          yaxis: { title: { text: 'Amplitude' }, gridcolor: '#2d3748' },
          height: 320,
          autosize: true,
        }}
        config={{ displaylogo: false, responsive: true }}
        style={{ width: '100%' }}
      />
      <Text fontSize="xs" color="gray.500" mt={1}>
        {total_samples.toLocaleString()} samples ({stride}× decimated)
      </Text>
    </Box>
  );
}
```

- [ ] **Step 3: Implement FFTPlot**

`apps/web/src/components/FFTPlot.tsx`:

```tsx
import { Box, Text } from '@chakra-ui/react';
import createPlotlyComponent from 'react-plotly.js/factory';
import Plotly from 'plotly.js-basic-dist';

import { useFFT } from '../api/queries';

const Plot = createPlotlyComponent(Plotly);

export function FFTPlot({ artifactId }: { artifactId: string }) {
  const q = useFFT(artifactId);
  if (q.isLoading) return <Text>Loading FFT…</Text>;
  if (q.isError || !q.data) return <Text color="red.400">Failed to load FFT</Text>;
  const { frequencies, magnitudes, sample_rate } = q.data;
  // Convert to dB for readability
  const dB = magnitudes.map((m) => 20 * Math.log10(Math.max(m, 1e-12)));
  return (
    <Box>
      <Plot
        data={[{ x: frequencies, y: dB, type: 'scatter', mode: 'lines', line: { color: '#fc8181', width: 1 } }]}
        layout={{
          paper_bgcolor: '#171923',
          plot_bgcolor: '#0a0e13',
          font: { color: '#e2e8f0' },
          margin: { l: 50, r: 20, t: 20, b: 40 },
          xaxis: { title: { text: 'Frequency (Hz)' }, gridcolor: '#2d3748' },
          yaxis: { title: { text: 'Magnitude (dB)' }, gridcolor: '#2d3748' },
          height: 320,
          autosize: true,
        }}
        config={{ displaylogo: false, responsive: true }}
        style={{ width: '100%' }}
      />
      <Text fontSize="xs" color="gray.500" mt={1}>
        Sample rate: {sample_rate} Hz
      </Text>
    </Box>
  );
}
```

- [ ] **Step 4: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/web/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(web): WaveformPlot and FFTPlot (Plotly) components"
```

---

### Task 7.2: RunDetailPage with test tree + plot panel

**Files:**

- Create: `apps/web/src/components/TestTree.tsx`
- Create: `apps/web/src/pages/RunDetailPage.tsx`
- Modify: `apps/web/src/App.tsx` (add `/runs/:id` route)

- [ ] **Step 1: Implement TestTree**

`apps/web/src/components/TestTree.tsx`:

```tsx
import { Box, Stack, Text } from '@chakra-ui/react';

import { useSuiteCases } from '../api/queries';
import type { SuiteSummary } from '../api/types';

const STATUS_DOT: Record<string, string> = {
  pass: '#48bb78',
  fail: '#f56565',
  error: '#f56565',
  skip: '#a0aec0',
};

interface Props {
  suites: SuiteSummary[];
  selectedCaseId: string | null;
  onSelectCase: (caseId: string) => void;
}

export function TestTree({ suites, selectedCaseId, onSelectCase }: Props) {
  return (
    <Stack gap={2}>
      {suites.map((s) => (
        <SuiteNode key={s.id} suite={s} selectedCaseId={selectedCaseId} onSelectCase={onSelectCase} />
      ))}
    </Stack>
  );
}

function SuiteNode({
  suite,
  selectedCaseId,
  onSelectCase,
}: {
  suite: SuiteSummary;
  selectedCaseId: string | null;
  onSelectCase: (caseId: string) => void;
}) {
  const q = useSuiteCases(suite.id);
  return (
    <Box>
      <Text fontSize="sm" fontWeight="600" color="gray.300" mb={1}>
        {suite.name}
      </Text>
      <Stack gap={0} pl={2}>
        {q.data?.map((c) => (
          <Box
            key={c.id}
            onClick={() => onSelectCase(c.id)}
            cursor="pointer"
            px={2}
            py={1}
            borderRadius="4px"
            bg={selectedCaseId === c.id ? '#2c5282' : 'transparent'}
            _hover={{ bg: selectedCaseId === c.id ? '#2c5282' : '#2d3748' }}
            fontSize="xs"
            color={selectedCaseId === c.id ? 'white' : '#cbd5e0'}
          >
            <Box as="span" display="inline-block" w="6px" h="6px" borderRadius="full" bg={STATUS_DOT[c.status]} mr={2} />
            {c.name}
          </Box>
        ))}
      </Stack>
    </Box>
  );
}
```

- [ ] **Step 2: Implement RunDetailPage**

`apps/web/src/pages/RunDetailPage.tsx`:

```tsx
import {
  Badge,
  Box,
  Grid,
  Heading,
  Stack,
  Tabs,
  Text,
} from '@chakra-ui/react';
import { useState } from 'react';
import { useParams } from 'react-router-dom';

import { useCase, useRun } from '../api/queries';
import { AppShell } from '../components/AppShell';
import { FFTPlot } from '../components/FFTPlot';
import { TestTree } from '../components/TestTree';
import { WaveformPlot } from '../components/WaveformPlot';

export function RunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);

  const runQuery = useRun(id);
  const caseQuery = useCase(selectedCaseId ?? undefined);

  const waveform = caseQuery.data?.artifacts.find((a) => a.kind.startsWith('waveform'));

  return (
    <AppShell>
      {runQuery.isLoading && <Text>Loading run…</Text>}
      {runQuery.isError && <Text color="red.400">Failed to load run</Text>}
      {runQuery.data && (
        <Box>
          <Heading size="lg" mb={2}>
            {runQuery.data.name}
          </Heading>
          <Stack direction="row" gap={2} mb={6}>
            <Badge colorPalette="blue">{runQuery.data.status}</Badge>
            {runQuery.data.tags.map((t) => (
              <Badge key={`${t.key}:${t.value}`} variant="outline">
                {t.key}={t.value}
              </Badge>
            ))}
          </Stack>
          <Grid templateColumns="240px 1fr" gap={4} minH="500px">
            <Box borderWidth={1} borderColor="#2d3748" borderRadius="md" p={3} bg="#171923" overflowY="auto">
              <TestTree
                suites={runQuery.data.suites}
                selectedCaseId={selectedCaseId}
                onSelectCase={setSelectedCaseId}
              />
            </Box>
            <Box borderWidth={1} borderColor="#2d3748" borderRadius="md" p={3} bg="#171923">
              {!selectedCaseId && <Text color="gray.500">Select a case from the tree</Text>}
              {selectedCaseId && caseQuery.isLoading && <Text>Loading case…</Text>}
              {caseQuery.data && (
                <Stack gap={3}>
                  <Box>
                    <Heading size="sm">{caseQuery.data.name}</Heading>
                    <Text fontSize="xs" color="gray.500">
                      {caseQuery.data.classname} · {caseQuery.data.status} · {caseQuery.data.duration_ms} ms
                    </Text>
                  </Box>
                  {caseQuery.data.failure_message && (
                    <Box bg="#2d1a1a" p={2} borderRadius="md" color="red.200" fontSize="sm">
                      {caseQuery.data.failure_message}
                    </Box>
                  )}
                  {waveform ? (
                    <Tabs.Root defaultValue="time">
                      <Tabs.List>
                        <Tabs.Trigger value="time">Time domain</Tabs.Trigger>
                        <Tabs.Trigger value="fft">FFT</Tabs.Trigger>
                      </Tabs.List>
                      <Tabs.Content value="time">
                        <WaveformPlot artifactId={waveform.id} />
                      </Tabs.Content>
                      <Tabs.Content value="fft">
                        <FFTPlot artifactId={waveform.id} />
                      </Tabs.Content>
                    </Tabs.Root>
                  ) : (
                    <Text color="gray.500" fontSize="sm">
                      No waveform artifact attached to this case.
                    </Text>
                  )}
                </Stack>
              )}
            </Box>
          </Grid>
        </Box>
      )}
    </AppShell>
  );
}
```

- [ ] **Step 3: Wire the route in App.tsx**

```tsx
import { RunDetailPage } from './pages/RunDetailPage';
// ...
<Route path="/runs/:id" element={<ProtectedRoute><RunDetailPage /></ProtectedRoute>} />
```

- [ ] **Step 4: Run tests + build**

```bash
cd /home/tcollins/dev/prism/apps/web && npm test && npm run build
```

- [ ] **Step 5: Commit**

```bash
cd /home/tcollins/dev/prism && git add apps/web/ && git -c user.email=travisfcollins@gmail.com -c user.name="Travis Collins" commit -m "feat(web): run detail page with test tree and time/FFT plot tabs"
```

---

## Phase 8: Full-stack verification

### Task 8.1: Rebuild & smoke test the whole stack

Manual — no commit.

- [ ] **Step 1: Rebuild and relaunch**

```bash
cd /home/tcollins/dev/prism && \
  docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml --env-file deploy/.env down && \
  docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml --env-file deploy/.env up -d --build
```

- [ ] **Step 2: Visit `http://localhost:8180`**, log in, navigate to Projects → audio → click a run → select a case → verify Time-domain and FFT tabs render plots.

- [ ] **Step 3: If you don't have example data in the DB yet, seed it (see Plan-3 addendum below).**

---

## Seed example data (optional post-plan helper)

To demonstrate the plot viewers, run this bash one-liner to generate a JUnit + a zip of synthetic waveforms and upload via the API. Assumes you're logged in (cookie at `/tmp/pc.txt`).

```bash
cd /home/tcollins/dev/prism && python3 - <<'PY'
import io, zipfile, numpy as np

fs = 48000
duration = 0.5
t = np.arange(int(fs * duration)) / fs

junit = b'''<?xml version="1.0"?>
<testsuites>
  <testsuite name="dsp" tests="3" failures="1" time="0.42">
    <testcase classname="codec" name="sine_sweep_1khz" time="0.12"/>
    <testcase classname="codec" name="sine_sweep_5khz" time="0.14">
      <failure message="expected SNR &gt;60dB, got 58.3dB">AssertionError</failure>
    </testcase>
    <testcase classname="latency" name="impulse_response" time="0.16"/>
  </testsuite>
</testsuites>'''

# Generate 3 waveforms
def csv_of(samples):
    return f"# sample_rate={fs}\n" + "\n".join(f"{x:.6f}" for x in samples)

w1 = np.sin(2*np.pi*1000*t)  # 1kHz sine
w2 = np.sin(2*np.pi*5000*t) + 0.3*np.sin(2*np.pi*12000*t)  # 5kHz + 12kHz
w3 = np.zeros_like(t); w3[0] = 1.0  # impulse

buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as zf:
    zf.writestr("dsp__sine_sweep_1khz__wave.csv", csv_of(w1))
    zf.writestr("dsp__sine_sweep_5khz__wave.csv", csv_of(w2))
    zf.writestr("dsp__impulse_response__wave.csv", csv_of(w3))

with open("/tmp/junit.xml", "wb") as f: f.write(junit)
with open("/tmp/arc.zip", "wb") as f: f.write(buf.getvalue())
print("wrote /tmp/junit.xml and /tmp/arc.zip")
PY

curl -s -c /tmp/pc.txt -H 'Content-Type: application/json' -d '{"email":"admin@example.com","password":"change-me-in-prod"}' http://localhost:8000/api/v1/auth/login
curl -s -b /tmp/pc.txt -H 'Content-Type: application/json' -d '{"slug":"audio","name":"Audio"}' http://localhost:8000/api/v1/projects
curl -s -b /tmp/pc.txt \
  -F 'junit=@/tmp/junit.xml;type=application/xml' \
  -F 'archive=@/tmp/arc.zip;type=application/zip' \
  -F 'metadata={"project_slug":"audio","name":"demo-run-1","tags":{"branch":"main","source":"seed"}}' \
  http://localhost:8000/api/v1/runs
```

After ~2 seconds the worker finishes ingesting and the run appears in the UI with all three cases; selecting `sine_sweep_1khz` → FFT should show a clean peak at 1000 Hz.
