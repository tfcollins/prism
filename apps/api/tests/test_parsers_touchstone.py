import math

import numpy as np

from prism_api.parsers.touchstone import is_touchstone, load_touchstone

# 2-port, MHz, MA format: S11 S21 S12 S22 (mag, angle each).
# S21 magnitudes: 0.5, 2.0 → -6.02 dB, +6.02 dB.
_S2P_MA = b"""! a filter
# MHZ S MA R 50
1000 0.1 0 0.5 30 0.5 -30 0.1 0
2000 0.1 0 2.0 45 2.0 -45 0.1 0
"""

# 1-port, GHz default (no option line specifies unit), DB format: S11 in dB.
_S1P_DB = b"""# GHZ S DB R 50
1.0 -3.0 12
2.0 -10.0 30
"""


def test_is_touchstone() -> None:
    assert is_touchstone("filter.s2p")
    assert is_touchstone("ANT.S1P")
    assert not is_touchstone("trace.csv")


def test_s2p_uses_s21_magnitude_in_db() -> None:
    spec = load_touchstone(_S2P_MA)
    assert spec.unit == "dB"
    assert spec.metadata["parameter"] == "S21"
    np.testing.assert_allclose(spec.frequencies, [1e9, 2e9])  # MHz scaled to Hz
    expected = [20 * math.log10(0.5), 20 * math.log10(2.0)]
    np.testing.assert_allclose(spec.powers, expected, atol=1e-9)


def test_s1p_db_format_uses_s11_directly() -> None:
    spec = load_touchstone(_S1P_DB)
    assert spec.metadata["parameter"] == "S11"
    np.testing.assert_allclose(spec.frequencies, [1e9, 2e9])  # GHz scaled to Hz
    np.testing.assert_allclose(spec.powers, [-3.0, -10.0])


# 1-port, RI format: S11 = real, imag. |3+4j| = 5 → 20*log10(5) ≈ 13.979 dB.
_S1P_RI = b"""# HZ S RI R 50
1000000000 3 4
"""


def test_s1p_ri_format_converts_to_db() -> None:
    spec = load_touchstone(_S1P_RI)
    assert spec.metadata["format"] == "RI"
    np.testing.assert_allclose(spec.frequencies, [1e9])  # Hz, no scaling
    np.testing.assert_allclose(spec.powers, [20 * math.log10(5.0)], atol=1e-9)
