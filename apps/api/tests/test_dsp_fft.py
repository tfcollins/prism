import hashlib

import numpy as np

from prism_api.dsp.fft import FFTParams, compute_fft, params_hash


def test_params_hash_stable() -> None:
    p1 = FFTParams(window="hann", nfft=1024, overlap=0.5)
    p2 = FFTParams(window="hann", nfft=1024, overlap=0.5)
    assert params_hash(p1) == params_hash(p2)


def test_params_hash_differs() -> None:
    assert params_hash(FFTParams(window="hann", nfft=1024, overlap=0.5)) != params_hash(
        FFTParams(window="hamming", nfft=1024, overlap=0.5)
    )


def test_compute_fft_finds_dominant_bin() -> None:
    fs = 8000
    t = np.arange(4096) / fs
    signal = np.sin(2 * np.pi * 1000 * t).astype(np.float64)
    result = compute_fft(signal, sample_rate=fs, params=FFTParams(window="hann", nfft=1024, overlap=0.5))
    assert len(result.frequencies) == len(result.magnitudes)
    peak_idx = int(np.argmax(result.magnitudes))
    peak_freq = result.frequencies[peak_idx]
    assert abs(peak_freq - 1000) < 50


def test_compute_fft_without_sample_rate_uses_unit_hz() -> None:
    result = compute_fft(np.ones(512), sample_rate=None, params=FFTParams(window="hann", nfft=256, overlap=0.5))
    # Without a sample rate we fall back to fs=1.0; peak at f=0 for constant signal
    assert result.sample_rate == 1.0
    assert result.frequencies[0] == 0.0
