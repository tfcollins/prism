import numpy as np

from prism_api.parsers.spectrum import is_spectrum_csv, load_spectrum

_SPEC_CSV = b"""# center=2.4e9
# span=20e6
# rbw=10e3
# unit=dBm
# detector=rms
2.39e9,-92.1
2.40e9,-10.2
2.41e9,-91.7
"""

_HEADER_CSV = b"""# center=100e6, span=1e6, rbw=1e3, unit=dBm
99.5e6,-80.0
100.0e6,-12.0
100.5e6,-79.5
"""

_WAVEFORM_CSV = b"""# sample_rate=48000
0.1
0.2
0.3
"""


def test_is_spectrum_csv_detects_two_column() -> None:
    assert is_spectrum_csv(_SPEC_CSV) is True
    assert is_spectrum_csv(_HEADER_CSV) is True


def test_is_spectrum_csv_rejects_waveform() -> None:
    assert is_spectrum_csv(_WAVEFORM_CSV) is False


def test_load_spectrum_columns_and_metadata() -> None:
    spec = load_spectrum(_SPEC_CSV)
    np.testing.assert_allclose(spec.frequencies, [2.39e9, 2.40e9, 2.41e9])
    np.testing.assert_allclose(spec.powers, [-92.1, -10.2, -91.7])
    assert spec.unit == "dBm"
    assert spec.metadata["center"] == 2.4e9
    assert spec.metadata["span"] == 20e6
    assert spec.metadata["rbw"] == 10e3
    assert spec.metadata["detector"] == "rms"


def test_load_spectrum_inline_header() -> None:
    spec = load_spectrum(_HEADER_CSV)
    assert spec.unit == "dBm"
    assert spec.metadata["center"] == 100e6
    assert len(spec.frequencies) == 3
