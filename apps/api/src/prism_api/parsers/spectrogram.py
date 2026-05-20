"""Spectrogram / waterfall loader: a 2D power[time, freq] matrix.

CSV format: one row per time frame, one column per frequency bin (so each row
has the same count C >= 3 of numeric columns — that is what distinguishes it
from a 1-column waveform or a 2-column spectrum). Optional ``# key=value``
metadata comments build the axes: ``f_start`` / ``f_stop`` (Hz) span the
frequency bins, ``t_start`` / ``t_step`` (s) the time frames; ``unit`` labels
the power. Absent metadata falls back to bin/frame indices.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from prism_api.parsers.spectrum import _comment_lines, _data_lines

_NUMERIC_META = {"f_start", "f_stop", "t_start", "t_step"}
_STRING_META = {"unit", "detector"}


def _parse_metadata(text: str) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    for raw in _comment_lines(text):
        for pair in re.split(r"[;,]", raw):
            if "=" not in pair:
                continue
            key, _, value = pair.partition("=")
            key = key.strip().lower()
            value = value.strip()
            if key in _NUMERIC_META:
                try:
                    meta[key] = float(value)
                except ValueError:
                    continue
            elif key in _STRING_META:
                meta[key] = value
    return meta


@dataclass
class Spectrogram:
    frequencies: np.ndarray  # 1-D float64, length C
    times: np.ndarray  # 1-D float64, length M
    powers: np.ndarray  # 2-D float64, shape (M, C)
    unit: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _numeric_row(line: str) -> list[float] | None:
    try:
        return [float(x) for x in line.split(",")]
    except ValueError:
        return None


def is_spectrogram_csv(data: bytes) -> bool:
    text = data.decode("utf-8", errors="replace")
    rows = _data_lines(text)
    if len(rows) < 2:
        return False
    widths: set[int] = set()
    for line in rows[:10]:
        nums = _numeric_row(line)
        if nums is None:
            return False
        widths.add(len(nums))
    return len(widths) == 1 and next(iter(widths)) >= 3


def load_spectrogram(data: bytes) -> Spectrogram:
    text = data.decode("utf-8", errors="replace")
    meta = _parse_metadata(text)
    matrix: list[list[float]] = []
    for line in _data_lines(text):
        nums = _numeric_row(line)
        if nums is not None:
            matrix.append(nums)
    powers = np.array(matrix, dtype=np.float64) if matrix else np.zeros((0, 0))
    n_frames, n_bins = powers.shape if powers.ndim == 2 and powers.size else (len(matrix), 0)

    f_start = meta.get("f_start")
    f_stop = meta.get("f_stop")
    if isinstance(f_start, float) and isinstance(f_stop, float) and n_bins:
        frequencies = np.linspace(f_start, f_stop, n_bins)
    else:
        frequencies = np.arange(n_bins, dtype=np.float64)

    t_start = meta.get("t_start", 0.0)
    t_step = meta.get("t_step", 1.0)
    t0 = float(t_start) if isinstance(t_start, (int, float)) else 0.0
    dt = float(t_step) if isinstance(t_step, (int, float)) else 1.0
    times = t0 + dt * np.arange(n_frames, dtype=np.float64)

    unit = meta.get("unit")
    return Spectrogram(
        frequencies=frequencies,
        times=times,
        powers=powers,
        unit=unit if isinstance(unit, str) else None,
        metadata=meta,
    )
