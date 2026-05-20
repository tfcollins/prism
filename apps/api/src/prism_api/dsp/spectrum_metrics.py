"""Channel-power / ACPR / OBW and spur detection over a (freq, power) spectrum.

Powers are treated as dBm samples, one per frequency bin. Band power is the sum
of the in-band bins in linear (mW) space — the standard integrated-channel-power
computation for an instrument trace already expressed in dBm-per-bin.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import find_peaks


def _dbm_to_mw(dbm: np.ndarray) -> np.ndarray:
    return np.power(10.0, dbm / 10.0)


def _mw_to_dbm(mw: float) -> float:
    return float(10.0 * np.log10(mw)) if mw > 0 else float("-inf")


def band_power_dbm(freqs: np.ndarray, powers_dbm: np.ndarray, lo: float, hi: float) -> float | None:
    """Integrated power (dBm) of all bins in [lo, hi], or None if the band is empty."""
    mask = (freqs >= lo) & (freqs <= hi)
    if not mask.any():
        return None
    total_mw = float(np.sum(_dbm_to_mw(powers_dbm[mask])))
    return _mw_to_dbm(total_mw)


@dataclass
class ChannelMetrics:
    channel_power_dbm: float | None
    acpr_lower_dbc: float | None
    acpr_upper_dbc: float | None
    obw_hz: float | None
    channel_band: tuple[float, float]
    lower_band: tuple[float, float] | None
    upper_band: tuple[float, float] | None


def occupied_bandwidth(
    freqs: np.ndarray, powers_dbm: np.ndarray, lo: float, hi: float, fraction: float = 0.99
) -> float | None:
    """Bandwidth (Hz) holding the central `fraction` of in-band power."""
    mask = (freqs >= lo) & (freqs <= hi)
    if mask.sum() < 2:
        return None
    f = freqs[mask]
    p = _dbm_to_mw(powers_dbm[mask])
    total = float(np.sum(p))
    if total <= 0:
        return None
    cdf = np.cumsum(p) / total
    tail = (1.0 - fraction) / 2.0
    lo_idx = int(np.searchsorted(cdf, tail))
    hi_idx = int(np.searchsorted(cdf, 1.0 - tail))
    lo_idx = min(lo_idx, len(f) - 1)
    hi_idx = min(hi_idx, len(f) - 1)
    return float(f[hi_idx] - f[lo_idx])


def channel_metrics(
    freqs: np.ndarray,
    powers_dbm: np.ndarray,
    *,
    center: float,
    channel_bw: float,
    offset: float | None = None,
    adjacent_bw: float | None = None,
) -> ChannelMetrics:
    half = channel_bw / 2.0
    ch_lo, ch_hi = center - half, center + half
    channel_power = band_power_dbm(freqs, powers_dbm, ch_lo, ch_hi)
    obw = occupied_bandwidth(freqs, powers_dbm, ch_lo, ch_hi)

    lower_band: tuple[float, float] | None = None
    upper_band: tuple[float, float] | None = None
    acpr_lower: float | None = None
    acpr_upper: float | None = None
    if offset is not None and adjacent_bw is not None:
        adj_half = adjacent_bw / 2.0
        lower_band = (center - offset - adj_half, center - offset + adj_half)
        upper_band = (center + offset - adj_half, center + offset + adj_half)
        lower_power = band_power_dbm(freqs, powers_dbm, *lower_band)
        upper_power = band_power_dbm(freqs, powers_dbm, *upper_band)
        if channel_power is not None and lower_power is not None:
            acpr_lower = lower_power - channel_power
        if channel_power is not None and upper_power is not None:
            acpr_upper = upper_power - channel_power

    return ChannelMetrics(
        channel_power_dbm=channel_power,
        acpr_lower_dbc=acpr_lower,
        acpr_upper_dbc=acpr_upper,
        obw_hz=obw,
        channel_band=(ch_lo, ch_hi),
        lower_band=lower_band,
        upper_band=upper_band,
    )


@dataclass
class Spur:
    frequency: float
    power: float


def find_spurs(
    freqs: np.ndarray, powers_dbm: np.ndarray, *, margin_db: float = 20.0, max_count: int = 25
) -> list[Spur]:
    """Peaks rising at least `margin_db` above the median noise floor.

    Returns the strongest `max_count` peaks, ordered by descending power.
    """
    if freqs.size == 0:
        return []
    floor = float(np.median(powers_dbm))
    threshold = floor + margin_db
    idx, _ = find_peaks(powers_dbm, height=threshold)
    spurs = [Spur(frequency=float(freqs[i]), power=float(powers_dbm[i])) for i in idx]
    spurs.sort(key=lambda s: s.power, reverse=True)
    return spurs[:max_count]
