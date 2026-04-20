"""Waveform loader tests: CSV, NPY, HDF5."""
import io

import h5py
import numpy as np
import pytest

from prism_api.models import ArtifactKind
from prism_api.parsers.waveform import load_waveform


def test_csv_single_column() -> None:
    data = b"0.0\n0.5\n-0.5\n"
    wf = load_waveform(ArtifactKind.WAVEFORM_CSV, data, filename="x.csv")
    assert np.allclose(wf.samples, [0.0, 0.5, -0.5])
    assert wf.sample_rate is None


def test_csv_with_header_and_sample_rate_inline() -> None:
    # Convention: a leading `# sample_rate=48000` comment is parsed as metadata
    data = b"# sample_rate=48000\n0.1\n0.2\n0.3\n"
    wf = load_waveform(ArtifactKind.WAVEFORM_CSV, data, filename="x.csv")
    assert wf.sample_rate == 48000
    assert np.allclose(wf.samples, [0.1, 0.2, 0.3])


def test_npy_load() -> None:
    buf = io.BytesIO()
    np.save(buf, np.array([0.1, 0.2, 0.3], dtype=np.float32))
    wf = load_waveform(ArtifactKind.WAVEFORM_NPY, buf.getvalue(), filename="x.npy")
    assert np.allclose(wf.samples, [0.1, 0.2, 0.3], atol=1e-7)


def test_hdf5_load_with_sample_rate_attr() -> None:
    buf = io.BytesIO()
    with h5py.File(buf, "w") as f:
        dset = f.create_dataset("waveform", data=np.array([0.0, 1.0, 2.0]))
        dset.attrs["sample_rate"] = 22050
    wf = load_waveform(ArtifactKind.WAVEFORM_HDF5, buf.getvalue(), filename="x.h5")
    assert np.allclose(wf.samples, [0.0, 1.0, 2.0])
    assert wf.sample_rate == 22050


def test_unsupported_kind_raises() -> None:
    with pytest.raises(ValueError):
        load_waveform(ArtifactKind.LOG_TEXT, b"hello", filename="x.log")
