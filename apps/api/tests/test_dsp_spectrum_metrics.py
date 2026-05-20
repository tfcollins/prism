import numpy as np
import pytest

from prism_api.dsp.spectrum_metrics import (
    band_power_dbm,
    channel_metrics,
    find_spurs,
)


def test_band_power_sums_linear_power() -> None:
    # Two bins at 0 dBm (=1 mW each) → total 2 mW → 3.0103 dBm
    freqs = np.array([100.0, 200.0, 300.0])
    powers = np.array([0.0, 0.0, -100.0])
    p = band_power_dbm(freqs, powers, 50.0, 250.0)
    assert p == pytest.approx(10 * np.log10(2.0), abs=1e-6)


def test_band_power_none_when_empty_band() -> None:
    freqs = np.array([100.0, 200.0])
    powers = np.array([0.0, 0.0])
    assert band_power_dbm(freqs, powers, 500.0, 600.0) is None


def test_channel_metrics_acpr() -> None:
    # Carrier band centered at 1000 with strong power; adjacent bands weaker.
    freqs = np.linspace(0, 2000, 2001)
    powers = np.full_like(freqs, -120.0)
    powers[(freqs >= 950) & (freqs <= 1050)] = -20.0  # channel
    powers[(freqs >= 750) & (freqs <= 850)] = -50.0  # lower adjacent
    powers[(freqs >= 1150) & (freqs <= 1250)] = -50.0  # upper adjacent

    m = channel_metrics(
        freqs, powers, center=1000.0, channel_bw=100.0, offset=200.0, adjacent_bw=100.0
    )
    assert m.channel_power_dbm is not None
    # adjacent is ~30 dB below channel power per bin; ACPR negative (dBc)
    assert m.acpr_lower_dbc is not None and m.acpr_lower_dbc < -25
    assert m.acpr_upper_dbc is not None and m.acpr_upper_dbc < -25
    assert m.acpr_lower_dbc == pytest.approx(m.acpr_upper_dbc, abs=0.5)


def test_channel_metrics_without_adjacent() -> None:
    freqs = np.linspace(0, 100, 101)
    powers = np.full_like(freqs, -50.0)
    m = channel_metrics(freqs, powers, center=50.0, channel_bw=20.0)
    assert m.channel_power_dbm is not None
    assert m.acpr_lower_dbc is None
    assert m.acpr_upper_dbc is None


def test_find_spurs_detects_peaks_above_floor() -> None:
    freqs = np.linspace(0, 1000, 1001)
    powers = np.full_like(freqs, -100.0)
    powers[500] = -10.0  # big spur
    powers[800] = -40.0  # smaller spur
    spurs = find_spurs(freqs, powers, margin_db=20.0)
    spur_freqs = sorted(round(s.frequency) for s in spurs)
    assert 500 in spur_freqs
    assert 800 in spur_freqs
    # The strongest spur is reported with its power
    strongest = max(spurs, key=lambda s: s.power)
    assert strongest.power == pytest.approx(-10.0)
