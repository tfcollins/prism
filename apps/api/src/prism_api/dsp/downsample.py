"""Downsample a waveform for plotting — preserves min/max within each bucket."""
from dataclasses import dataclass

import numpy as np


@dataclass
class DownsampledSeries:
    samples: np.ndarray
    stride: int


def downsample_for_plot(samples: np.ndarray, *, target: int) -> DownsampledSeries:
    """Reduce `samples` to approximately `target` points using min/max pairing.

    Each output bucket contributes two points (min, then max) so fast transients
    stay visible. If the input already fits, it's returned unchanged.
    """
    n = len(samples)
    if n <= target:
        return DownsampledSeries(samples=samples, stride=1)

    # Two points per bucket -> bucket count ≈ target/2
    bucket_count = max(1, target // 2)
    stride = max(1, n // bucket_count)
    # Trim so samples divides evenly by stride
    end = (n // stride) * stride
    reshaped = samples[:end].reshape(-1, stride)
    mins = reshaped.min(axis=1)
    maxs = reshaped.max(axis=1)
    # Interleave (min, max) per bucket
    interleaved = np.empty(mins.size + maxs.size, dtype=samples.dtype)
    interleaved[0::2] = mins
    interleaved[1::2] = maxs
    return DownsampledSeries(samples=interleaved, stride=stride)
