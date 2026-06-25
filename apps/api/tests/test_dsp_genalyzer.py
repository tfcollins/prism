import math

import numpy as np

from prism_api.dsp.genalyzer_markers import analyze


def test_analyze_finds_fundamental_harmonic_and_metrics() -> None:
    fs = 48000.0
    n = 24000
    t = np.arange(n) / fs
    # 1500 Hz tone with a small 3rd harmonic at 4500 Hz.
    sig = np.sin(2 * math.pi * 1500 * t) + 0.01 * np.sin(2 * math.pi * 4500 * t)

    r = analyze(sig, fs, harmonics=5)

    labels = {m.label for m in r.markers}
    assert "Fund" in labels
    fund = next(m for m in r.markers if m.label == "Fund")
    assert abs(fund.frequency - 1500.0) < 50.0  # within a few bins
    assert any(m.label.startswith("HD") for m in r.markers)

    assert r.snr is not None and r.snr > 30.0
    assert r.sfdr is not None
    assert r.enob is not None  # derived from SINAD


def test_analyze_silence_is_degenerate_not_an_error() -> None:
    r = analyze(np.zeros(1024), 48000.0)
    assert r.markers == []
    assert r.snr is None and r.enob is None
