from prism_api.models import ArtifactKind
from prism_api.parsers.detect import detect_kind


def test_junit_xml() -> None:
    assert (
        detect_kind("results.xml", b'<?xml version="1.0"?><testsuites/>') == ArtifactKind.JUNIT_XML
    )


def test_waveform_csv() -> None:
    assert detect_kind("sine.csv", b"0.0\n0.1\n0.2\n") == ArtifactKind.WAVEFORM_CSV


def test_waveform_npy() -> None:
    # magic: \x93NUMPY
    assert detect_kind("wave.npy", b"\x93NUMPY\x01\x00") == ArtifactKind.WAVEFORM_NPY


def test_waveform_hdf5() -> None:
    # magic: \x89HDF\r\n\x1a\n
    assert detect_kind("data.h5", b"\x89HDF\r\n\x1a\n") == ArtifactKind.WAVEFORM_HDF5


def test_wav_audio() -> None:
    assert detect_kind("clip.wav", b"RIFF....WAVEfmt ") == ArtifactKind.WAV_AUDIO


def test_png_image() -> None:
    assert detect_kind("plot.png", b"\x89PNG\r\n\x1a\n") == ArtifactKind.IMAGE_PNG


def test_text_log() -> None:
    assert detect_kind("run.log", b"2026-04-20 12:00:00 info\n") == ArtifactKind.LOG_TEXT


def test_other_binary() -> None:
    assert detect_kind("mystery.bin", b"\x00\x01\x02\x03") == ArtifactKind.OTHER_BINARY


def test_extension_overrides_ambiguous_magic() -> None:
    # An .xml file should still be JUnit even if content is missing leading <?xml
    assert detect_kind("x.xml", b"<testsuites><testsuite/></testsuites>") == ArtifactKind.JUNIT_XML
