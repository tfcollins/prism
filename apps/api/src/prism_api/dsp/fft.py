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


def compute_fft(
    samples: np.ndarray, *, sample_rate: int | float | None, params: FFTParams
) -> FFTResult:
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
    return FFTResult(
        frequencies=freqs.astype(np.float64),
        magnitudes=magnitudes.astype(np.float64),
        sample_rate=fs,
    )
