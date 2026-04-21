import numpy as np

from prism_api.dsp.downsample import downsample_for_plot


def test_pass_through_if_already_small() -> None:
    samples = np.arange(100, dtype=np.float64)
    got = downsample_for_plot(samples, target=500)
    assert np.array_equal(got.samples, samples)
    assert got.stride == 1


def test_decimates_to_roughly_target_size() -> None:
    samples = np.arange(10_000, dtype=np.float64)
    got = downsample_for_plot(samples, target=1_000)
    assert abs(len(got.samples) - 1_000) <= 10
    assert got.stride >= 10


def test_preserves_peaks_with_minmax_pair() -> None:
    # Generate a sine with fast spikes; min/max pairing should preserve extremes
    t = np.arange(10_000, dtype=np.float64)
    samples = np.sin(t / 100) + 0.1 * np.sin(t * 5)
    got = downsample_for_plot(samples, target=400)
    assert abs(got.samples.max() - samples.max()) < 0.05
    assert abs(got.samples.min() - samples.min()) < 0.05
