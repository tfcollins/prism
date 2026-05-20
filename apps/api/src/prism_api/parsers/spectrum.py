"""Spectrum loader for instrument CSV exports.

A spectrum CSV is two columns ``frequency,power`` with an optional metadata
header of ``# key=value`` comment lines (``center``, ``span``, ``rbw``, ``vbw``,
``ref_level``, ``unit``, ``detector``, ``sweep_time``). Both one-per-line and a
single comma-separated header line are accepted. This is distinct from a
waveform CSV, which is a single column of samples with an optional
``# sample_rate=`` comment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np

_NUMERIC_META = {"center", "span", "rbw", "vbw", "ref_level", "sweep_time"}
_STRING_META = {"unit", "detector"}


@dataclass
class Spectrum:
    frequencies: np.ndarray  # 1-D float64, Hz
    powers: np.ndarray  # 1-D float64
    unit: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _comment_lines(text: str) -> list[str]:
    return [line.lstrip("#").strip() for line in text.splitlines() if line.lstrip().startswith("#")]


def _data_lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _parse_metadata(text: str) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    for raw in _comment_lines(text):
        # Support both "key=value" alone and "k1=v1, k2=v2" on one line.
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


def is_spectrum_csv(data: bytes) -> bool:
    """True when the CSV looks like a (frequency, power) spectrum rather than a waveform."""
    text = data.decode("utf-8", errors="replace")
    data_lines = _data_lines(text)
    if not data_lines:
        return False
    # Every data row of a spectrum has two numeric, comma-separated columns.
    checked = 0
    for line in data_lines[:10]:
        parts = line.split(",")
        if len(parts) != 2:
            return False
        try:
            float(parts[0])
            float(parts[1])
        except ValueError:
            return False
        checked += 1
    return checked > 0


def load_spectrum(data: bytes) -> Spectrum:
    text = data.decode("utf-8", errors="replace")
    meta = _parse_metadata(text)
    freqs: list[float] = []
    powers: list[float] = []
    for line in _data_lines(text):
        parts = line.split(",")
        if len(parts) != 2:
            continue
        try:
            f, p = float(parts[0]), float(parts[1])
        except ValueError:
            continue
        freqs.append(f)
        powers.append(p)
    unit = meta.get("unit")
    return Spectrum(
        frequencies=np.array(freqs, dtype=np.float64),
        powers=np.array(powers, dtype=np.float64),
        unit=unit if isinstance(unit, str) else None,
        metadata=meta,
    )
