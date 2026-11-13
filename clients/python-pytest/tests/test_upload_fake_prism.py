"""L4: end-to-end multipart upload against the in-process fake Prism."""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from pytest_prism.config import Config
from pytest_prism.manifest import OutputDir
from pytest_prism.upload import UploadError, upload
from tests.conftest import FakePrismRecord


def _seeded_out(tmp_path: Path) -> OutputDir:
    od = OutputDir(tmp_path / "out")
    od.initialize()
    (od.root / "junit.xml").write_text(
        '<testsuite name="suite_x"><testcase classname="t" name="case_a"/></testsuite>'
    )
    od.write_run_artifact("dmesg_pre.log", b"pre\n", kind="dmesg_pre")
    od.write_case_artifact(
        case_nodeid="t::case_a",
        filename="spectrum.html",
        content=b"<html/>",
        kind="adi.iq",
    )
    od.write_case_artifact(
        case_nodeid="t::case_a",
        filename="metrics.json",
        content=b"{}",
        kind="adi.iq",
    )
    od.finalize(run_meta={"plugin_version": "0.1.0"})
    return od


def _cfg(url: str) -> Config:
    return Config.from_argv(
        [
            "--prism-report",
            "--prism-url",
            url,
            "--prism-email",
            "u@x",
            "--prism-password",
            "pw",
            "--prism-project",
            "demo",
        ]
    )


def test_happy_path_upload(tmp_path: Path, fake_prism: tuple[str, FakePrismRecord]) -> None:
    url, record = fake_prism
    od = _seeded_out(tmp_path)
    cfg = _cfg(url)
    result = upload(od, cfg, poll_timeout_s=2.0, poll_interval_s=0.05)
    assert result.run_id == "run-1"
    assert result.status == "ready"
    assert len(record.runs) == 1
    assert len(record.multipart_bodies) == 1
    body = record.multipart_bodies[0]
    assert b'name="junit"' in body
    assert b'name="archive"' in body


def test_archive_uses_kind_in_arcname(
    tmp_path: Path, fake_prism: tuple[str, FakePrismRecord]
) -> None:
    """Per-case files are renamed to {suite}__{case}__{kind}__{filename}."""
    url, record = fake_prism
    od = _seeded_out(tmp_path)
    cfg = _cfg(url)
    upload(od, cfg, poll_timeout_s=2.0, poll_interval_s=0.05)
    body = record.multipart_bodies[0]
    # Extract the embedded zip (multipart parsing is annoying — use a marker)
    marker = b"Content-Type: application/zip\r\n\r\n"
    start = body.index(marker) + len(marker)
    end = body.index(b"\r\n--", start)
    zip_bytes = body[start:end]
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        names = set(zf.namelist())
    assert "suite_x__case_a__adi.iq__spectrum.html" in names
    assert "suite_x__case_a__adi.iq__metrics.json" in names
    assert "dmesg_pre.log" in names


def test_fail_on_upload_error_propagates(
    tmp_path: Path, fake_prism: tuple[str, FakePrismRecord]
) -> None:
    url, record = fake_prism
    record.next_status_code = 500
    od = _seeded_out(tmp_path)
    cfg = _cfg(url)

    with pytest.raises(UploadError, match="run create failed"):
        upload(od, cfg, poll_timeout_s=2.0, poll_interval_s=0.05)


def test_polls_until_ready(tmp_path: Path, fake_prism: tuple[str, FakePrismRecord]) -> None:
    """Status starts pending, then flips to ready on a later poll."""
    import threading

    url, record = fake_prism
    record.next_status_value = "pending"

    # Flip to ready after a short delay using a background thread.
    def _flip() -> None:
        import time as _t

        _t.sleep(0.15)
        record.next_status_value = "ready"

    threading.Thread(target=_flip, daemon=True).start()

    od = _seeded_out(tmp_path)
    cfg = _cfg(url)
    result = upload(od, cfg, poll_timeout_s=2.0, poll_interval_s=0.05)
    assert result.status == "ready"


def test_archive_keeps_same_named_tests_distinct(tmp_path: Path) -> None:
    import json

    from pytest_prism.upload import _build_artifacts_zip

    od = OutputDir(tmp_path / "out")
    od.initialize()
    (od.root / "junit.xml").write_text(
        "<testsuites>"
        '<testsuite name="pytest">'
        '<testcase classname="test_a" name="test_same">'
        "<properties>"
        '<property name="prism_nodeid" value="test_a.py::test_same"/>'
        "</properties>"
        "</testcase>"
        '<testcase classname="test_b" name="test_same">'
        "<properties>"
        '<property name="prism_nodeid" value="test_b.py::test_same"/>'
        "</properties>"
        "</testcase>"
        "</testsuite>"
        "</testsuites>"
    )
    for module in ["test_a", "test_b"]:
        od.write_case_artifact(
            case_nodeid=f"{module}.py::test_same",
            filename="pytest_stdout_call.log",
            content=module.encode(),
            kind="pytest_capture",
        )
    od.finalize(run_meta={})
    with zipfile.ZipFile(BytesIO(_build_artifacts_zip(od.root))) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        entries = manifest["archive_artifacts"]
        assert {entry["classname"] for entry in entries} == {"test_a", "test_b"}
        assert len({entry["filename"] for entry in entries}) == 2
        for entry in entries:
            assert zf.read(entry["filename"]).decode() == entry["classname"]
