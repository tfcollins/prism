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
    if suffix == ".csv":
        return ArtifactKind.WAVEFORM_CSV
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
