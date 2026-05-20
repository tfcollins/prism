"""Artifact kind detection — extension + magic bytes."""

from pathlib import PurePosixPath

from prism_api.models import ArtifactKind


def _has_prefix(data: bytes, prefix: bytes) -> bool:
    return data.startswith(prefix)


def _is_probably_text(data: bytes) -> bool:
    sample = data[:1024]
    return all(32 <= b < 127 or b in (9, 10, 13) for b in sample)


def detect_kind(filename: str, head: bytes) -> ArtifactKind:
    """Detect artifact kind by trusting magic bytes first, then extension, then content."""
    # Magic-byte fast paths
    if _has_prefix(head, b"\x93NUMPY"):
        return ArtifactKind.WAVEFORM_NPY
    if _has_prefix(head, b"\x89HDF\r\n\x1a\n"):
        return ArtifactKind.WAVEFORM_HDF5
    if _has_prefix(head, b"\x89PNG\r\n\x1a\n"):
        return ArtifactKind.IMAGE_PNG
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return ArtifactKind.WAV_AUDIO

    # Extension-based
    suffix = PurePosixPath(filename).suffix.lower()
    if suffix == ".xml":
        return ArtifactKind.JUNIT_XML
    if suffix in {".s1p", ".s2p"}:
        return ArtifactKind.SPECTRUM_TOUCHSTONE
    if suffix == ".csv":
        # Distinguish, by column shape: a wide matrix (>=3 numeric cols, many
        # rows) is a spectrogram; two columns a (frequency, power) spectrum;
        # otherwise a single-column waveform.
        from prism_api.parsers.spectrogram import is_spectrogram_csv
        from prism_api.parsers.spectrum import is_spectrum_csv

        if is_spectrogram_csv(head):
            return ArtifactKind.SPECTROGRAM
        return ArtifactKind.SPECTRUM_CSV if is_spectrum_csv(head) else ArtifactKind.WAVEFORM_CSV
    if suffix in {".npy"}:
        return ArtifactKind.WAVEFORM_NPY
    if suffix in {".h5", ".hdf5"}:
        return ArtifactKind.WAVEFORM_HDF5
    if suffix == ".wav":
        return ArtifactKind.WAV_AUDIO
    if suffix == ".png":
        return ArtifactKind.IMAGE_PNG
    if suffix in {".log", ".txt"}:
        return ArtifactKind.LOG_TEXT

    # Content-based fallbacks
    if _is_probably_text(head):
        return ArtifactKind.LOG_TEXT
    return ArtifactKind.OTHER_BINARY
