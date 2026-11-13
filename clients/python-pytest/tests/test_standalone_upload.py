"""Standalone CLI forwards metadata and keeps full transcripts in its archive."""

import importlib.util
import json
import zipfile
from io import BytesIO
from pathlib import Path
from types import ModuleType

import pytest

from tests.conftest import FakePrismRecord


def uploader() -> ModuleType:
    path = Path(__file__).resolve().parents[3] / "scripts" / "upload_run.py"
    spec = importlib.util.spec_from_file_location("standalone_uploader", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_standalone_metadata_and_complete_transcript(
    tmp_path: Path, fake_prism: tuple[str, FakePrismRecord], monkeypatch: pytest.MonkeyPatch
) -> None:
    module = uploader()
    url, record = fake_prism
    monkeypatch.setattr(module.PrismClient, "project_exists", lambda *a: True)
    junit = tmp_path / "junit.xml"
    junit.write_text("<testsuites/>")
    log = tmp_path / "pytest.log"
    full_log = "".join(f"line {i}\n" for i in range(6001))
    log.write_text(full_log)
    hw = tmp_path / "hardware.json"
    hw.write_text('{"place":"reserved","collection_errors":["dmesg unavailable"]}')
    archive = tmp_path / "archive.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("dmesg_pre.log", "before testing\n")
    assert (
        module.main(
            [
                str(junit),
                "--url",
                url,
                "--token",
                "token",
                "--project",
                "demo",
                "--run-name",
                "run",
                "--ci-json",
                '{"provider":"other"}',
                "--hardware-json",
                str(hw),
                "--job-url",
                "https://ci.example/job",
                "--pytest-log",
                str(log),
                "--archive",
                str(archive),
            ]
        )
        == 0
    )
    body = record.multipart_bodies[0]
    meta = json.loads(body.split(b'name="metadata"\r\n\r\n')[1].split(b"\r\n--")[0])
    assert meta["hardware"]["place"] == "reserved"
    assert meta["ci"] == {"provider": "other", "job_url": "https://ci.example/job"}
    raw_zip = body.split(b"Content-Type: application/zip\r\n\r\n")[1].split(b"\r\n--")[0]
    with zipfile.ZipFile(BytesIO(raw_zip)) as zf:
        assert zf.read("terminal.log").decode() == full_log
        assert zf.read("dmesg_pre.log") == b"before testing\n"


def test_custom_workflow_command_inherits_capture_environment(
    tmp_path: Path, fake_prism: tuple[str, FakePrismRecord], monkeypatch: pytest.MonkeyPatch
) -> None:
    module = uploader()
    url, record = fake_prism
    monkeypatch.setattr(module.PrismClient, "project_exists", lambda *a: True)
    junit = tmp_path / "junit.xml"
    junit.write_text("<testsuites/>")
    log = tmp_path / "terminal.log"
    log.write_text("full transcript from custom uploader\n")
    hw = tmp_path / "hardware.json"
    hw.write_text('{"place":"reserved"}')
    archive = tmp_path / "capture.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("dmesg_post.log", "after\n")
    monkeypatch.setenv("PRISM_HARDWARE_JSON", str(hw))
    monkeypatch.setenv("PRISM_PYTEST_LOG", str(log))
    monkeypatch.setenv("PRISM_ARCHIVE", str(archive))
    assert (
        module.main(
            [
                str(junit),
                "--url",
                url,
                "--token",
                "token",
                "--project",
                "demo",
                "--run-name",
                "custom",
            ]
        )
        == 0
    )
    body = record.multipart_bodies[0]
    raw_zip = body.split(b"Content-Type: application/zip\r\n\r\n")[1].split(b"\r\n--")[0]
    with zipfile.ZipFile(BytesIO(raw_zip)) as zf:
        assert zf.read("terminal.log") == log.read_bytes()
        assert zf.read("dmesg_post.log") == b"after\n"
