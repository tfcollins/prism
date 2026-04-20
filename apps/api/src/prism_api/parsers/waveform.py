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
    # Use list comprehension instead of np.fromstring to avoid DeprecationWarning
    values = np.array([float(line) for line in rows], dtype=np.float64) if rows else np.empty(0)
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
