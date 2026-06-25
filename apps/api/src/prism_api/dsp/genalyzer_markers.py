"""Genalyzer-based FFT markers + metrics for a captured waveform.

Wraps the ADI genalyzer library: quantizes the (float) samples to 16-bit codes,
runs a real-input FFT analysis, and returns the labeled tone markers
(fundamental, harmonics, DC, worst spur) plus SNR/SFDR/SINAD/THD/ENOB.

genalyzer keeps process-global analysis state keyed by string and ``ctypes``-loads
``libgenalyzer``; calls are serialized under a module lock. The import is lazy so
the rest of the app/tests do not require ``libgenalyzer`` to be present.
"""

from __future__ import annotations

import math
import re
import threading
from dataclasses import dataclass, field

import numpy as np

_LOCK = threading.Lock()
_FRIENDLY = {"dc": "DC", "A": "Fund", "wo": "Worst spur"}
_HD = re.compile(r"^(\d+)A$")


@dataclass
class Marker:
    label: str
    frequency: float
    mag_dbfs: float


@dataclass
class GenalyzerResult:
    markers: list[Marker] = field(default_factory=list)
    snr: float | None = None
    sfdr: float | None = None
    sinad: float | None = None
    thd: float | None = None
    enob: float | None = None
    fsnr: float | None = None


def _friendly(label: str) -> str:
    if label in _FRIENDLY:
        return _FRIENDLY[label]
    m = _HD.match(label)
    return f"HD{m.group(1)}" if m else label


def _thd_dbc(results: dict[str, float], harmonics: int) -> float | None:
    """THD (dBc) = power sum of the harmonic magnitudes relative to the carrier."""
    power = 0.0
    found = False
    for k in range(2, harmonics + 1):
        v = results.get(f"{k}A:mag_dbc")
        if v is not None:
            power += 10.0 ** (float(v) / 10.0)
            found = True
    if not found or power <= 0.0:
        return None
    return 10.0 * math.log10(power)


def analyze(
    samples: np.ndarray,
    sample_rate: float,
    *,
    harmonics: int = 5,
    window: str = "blackman_harris",
) -> GenalyzerResult:
    """Run genalyzer FFT analysis on a real waveform; degenerate input → empty."""
    x = np.asarray(samples, dtype=np.float64).ravel()
    if x.size < 4:
        return GenalyzerResult()
    nfft = 1 << math.floor(math.log2(x.size))
    x = x[:nfft]
    peak = float(np.max(np.abs(x)))
    if peak <= 0.0:
        return GenalyzerResult()

    import genalyzer as gn

    win_map = {
        "blackman_harris": gn.Window.BLACKMAN_HARRIS,
        "hann": gn.Window.HANN,
        "none": gn.Window.NO_WINDOW,
    }
    gn_window = win_map.get(window, gn.Window.BLACKMAN_HARRIS)
    # NO_WINDOW assumes coherent sampling — no leakage skirt, so ssb=0.
    ssb = 0 if gn_window == gn.Window.NO_WINDOW else 3

    fsr = 2.0 * peak * 1.0001
    with _LOCK:
        qwf = gn.quantize(x, fsr, 16, 0.0, gn.CodeFormat.TWOS_COMPLEMENT)
        fft_cplx = gn.rfft(
            qwf,
            16,
            1,
            nfft,
            gn_window,
            gn.CodeFormat.TWOS_COMPLEMENT,
            gn.RfftScale.DBFS_SIN,
        )
        key = "prism_fa"
        gn.mgr_remove(key)
        gn.fa_create(key)
        gn.fa_analysis_band(key, "fdata*0.0", "fdata*1.0")
        gn.fa_max_tone(key, "A", gn.FaCompTag.SIGNAL, ssb)
        gn.fa_hd(key, harmonics)
        gn.fa_ssb(key, gn.FaSsb.DEFAULT, ssb)
        gn.fa_fsample(key, sample_rate)
        results = gn.fft_analysis(key, fft_cplx, nfft)
        annots = gn.fa_annotations(results)
        gn.mgr_remove(key)

    markers = [
        Marker(label=_friendly(str(lab)), frequency=float(freq), mag_dbfs=float(mag))
        for freq, mag, lab in annots["labels"]
    ]

    def _get(k: str) -> float | None:
        v = results.get(k)
        return float(v) if v is not None else None

    sinad = _get("sinad")
    enob = (sinad - 1.76) / 6.02 if sinad is not None else None
    return GenalyzerResult(
        markers=markers,
        snr=_get("snr"),
        sfdr=_get("sfdr"),
        sinad=sinad,
        thd=_thd_dbc(results, harmonics),
        enob=enob,
        fsnr=_get("fsnr"),
    )
