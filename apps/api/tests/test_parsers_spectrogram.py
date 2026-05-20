import numpy as np

from prism_api.models import ArtifactKind
from prism_api.parsers.detect import detect_kind
from prism_api.parsers.spectrogram import is_spectrogram_csv, load_spectrogram

_SG = b"""# f_start=1e9, f_stop=2e9
# t_start=0, t_step=0.5
# unit=dBm
-90,-85,-80
-88,-70,-60
-91,-86,-82
"""


def test_is_spectrogram_csv() -> None:
    assert is_spectrogram_csv(_SG) is True
    # spectrum (2 columns) and waveform (1 column) are not spectrograms
    assert is_spectrogram_csv(b"1e9,-90\n2e9,-80\n") is False
    assert is_spectrogram_csv(b"0.1\n0.2\n0.3\n") is False


def test_detect_routes_wide_csv_to_spectrogram() -> None:
    assert detect_kind("waterfall.csv", _SG) == ArtifactKind.SPECTROGRAM


def test_load_spectrogram_builds_axes() -> None:
    sg = load_spectrogram(_SG)
    assert sg.unit == "dBm"
    assert sg.powers.shape == (3, 3)
    np.testing.assert_allclose(sg.frequencies, [1e9, 1.5e9, 2e9])
    np.testing.assert_allclose(sg.times, [0.0, 0.5, 1.0])
    np.testing.assert_allclose(sg.powers[1], [-88, -70, -60])


def test_load_spectrogram_falls_back_to_indices() -> None:
    sg = load_spectrogram(b"1,2,3\n4,5,6\n")
    np.testing.assert_allclose(sg.frequencies, [0, 1, 2])
    np.testing.assert_allclose(sg.times, [0, 1])
