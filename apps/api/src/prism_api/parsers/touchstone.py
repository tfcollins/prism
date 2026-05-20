"""Touchstone (.s1p/.s2p) reader, surfaced as a spectrum trace.

A Touchstone file is an instrument export of S-parameters versus frequency. For
the spectrum & power use case we treat the transmission magnitude as a spectrum:
``S21`` for a 2-port (amplifier/filter response) and ``S11`` for a 1-port
(reflection). Phase is discarded.

Format per the Touchstone spec: ``!`` comment lines, an optional option line
``# <freq-unit> <param> <format> R <z0>`` (default ``GHZ S MA R 50``), then data
rows ``freq <pair>...`` where each S-parameter is two columns whose meaning
depends on the format (MA: mag/angle, DB: dB/angle, RI: real/imag).
"""

from __future__ import annotations

import math

import numpy as np

from prism_api.parsers.spectrum import Spectrum

_FREQ_SCALE = {"HZ": 1.0, "KHZ": 1e3, "MHZ": 1e6, "GHZ": 1e9}
_MAG_FLOOR = 1e-12  # avoid log10(0) → -inf for a perfect null


def _to_db(a: float, b: float, fmt: str) -> float:
    if fmt == "DB":
        return a
    mag = math.hypot(a, b) if fmt == "RI" else a  # RI: |re+jim|; MA: mag column
    return 20.0 * math.log10(max(mag, _MAG_FLOOR))


def is_touchstone(filename: str) -> bool:
    name = filename.lower()
    return name.endswith((".s1p", ".s2p"))


def load_touchstone(data: bytes) -> Spectrum:
    text = data.decode("utf-8", errors="replace")
    freq_unit = "GHZ"
    fmt = "MA"
    rows: list[list[float]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("!"):
            continue
        if line.startswith("#"):
            tokens = line[1:].upper().split()
            for t in tokens:
                if t in _FREQ_SCALE:
                    freq_unit = t
                elif t in {"MA", "DB", "RI"}:
                    fmt = t
            continue
        # numeric data row: freq followed by S-parameter pairs
        try:
            nums = [float(x) for x in line.replace(",", " ").split()]
        except ValueError:
            continue
        if len(nums) >= 3:
            rows.append(nums)

    freqs: list[float] = []
    powers: list[float] = []
    scale = _FREQ_SCALE[freq_unit]
    # S21 is the second parameter (cols 3,4) for a 2-port; for a 1-port the only
    # parameter S11 is cols 1,2. Distinguish by column count.
    for nums in rows:
        n_pairs = (len(nums) - 1) // 2
        idx = 1 if n_pairs >= 2 else 0  # 0 → S11, 1 → S21
        a = nums[1 + 2 * idx]
        b = nums[2 + 2 * idx]
        freqs.append(nums[0] * scale)
        powers.append(_to_db(a, b, fmt))

    param = "S21" if rows and (len(rows[0]) - 1) // 2 >= 2 else "S11"
    return Spectrum(
        frequencies=np.array(freqs, dtype=np.float64),
        powers=np.array(powers, dtype=np.float64),
        unit="dB",
        metadata={"parameter": param, "format": fmt},
    )
