"""Unit tests for OutputDir and manifest.json schema (v2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pytest_prism.manifest import OutputDir, _safe_test_id


def test_safe_test_id_basic() -> None:
    assert _safe_test_id("test/foo.py::test_bar") == "test_foo.py__test_bar"


def test_safe_test_id_replaces_unsafe_chars() -> None:
    sid = _safe_test_id("test/foo.py::test_bar[a/b c]")
    assert "/" not in sid
    assert " " not in sid


def test_safe_test_id_caps_length() -> None:
    long = "x" * 500
    sid = _safe_test_id(long)
    assert len(sid) <= 200


def test_initialize_refuses_non_empty_dir(tmp_path: Path) -> None:
    (tmp_path / "junk").write_text("hi")
    od = OutputDir(tmp_path)
    with pytest.raises(SystemExit):
        od.initialize()


def test_initialize_creates_cases_subdir(tmp_path: Path) -> None:
    root = tmp_path / "out"
    od = OutputDir(root)
    od.initialize()
    assert (root / "cases").is_dir()


def test_run_artifact_written_to_root(tmp_path: Path) -> None:
    root = tmp_path / "out"
    od = OutputDir(root)
    od.initialize()
    od.write_run_artifact("boot.log", b"line1\n", kind="boot_log")
    assert (root / "boot.log").read_bytes() == b"line1\n"


def test_case_artifact_written_under_per_kind_subdir(tmp_path: Path) -> None:
    root = tmp_path / "out"
    od = OutputDir(root)
    od.initialize()
    od.write_case_artifact(
        case_nodeid="t::a",
        filename="spectrum.html",
        content=b"<html/>",
        kind="adi.iq",
    )
    assert (root / "cases" / "t__a" / "adi.iq" / "spectrum.html").read_bytes() == b"<html/>"


def test_two_kinds_under_same_case(tmp_path: Path) -> None:
    root = tmp_path / "out"
    od = OutputDir(root)
    od.initialize()
    od.write_case_artifact(case_nodeid="t::a", filename="a.html", content=b"<a/>", kind="kindA")
    od.write_case_artifact(case_nodeid="t::a", filename="b.html", content=b"<b/>", kind="kindB")
    assert (root / "cases" / "t__a" / "kindA" / "a.html").exists()
    assert (root / "cases" / "t__a" / "kindB" / "b.html").exists()


def test_record_case_artifact_does_not_double_write(tmp_path: Path) -> None:
    """record_case_artifact registers an existing file in the manifest."""
    root = tmp_path / "out"
    od = OutputDir(root)
    od.initialize()
    case_dir = od.case_kind_dir(case_nodeid="t::a", kind="adi.iq")
    (case_dir / "spectrum.html").write_bytes(b"<html>1234567</html>")
    od.record_case_artifact(case_nodeid="t::a", filename="spectrum.html", kind="adi.iq")
    manifest = od.finalize(run_meta={})
    art = manifest["cases"][0]["artifacts"][0]
    assert art["filename"] == "spectrum.html"
    assert art["kind"] == "adi.iq"
    assert art["size"] == 20
    assert art["rel_path"] == "cases/t__a/adi.iq/spectrum.html"


def test_finalize_writes_manifest_v2(tmp_path: Path) -> None:
    root = tmp_path / "out"
    od = OutputDir(root)
    od.initialize()
    od.write_run_artifact("dmesg_pre.log", b"x", kind="dmesg_pre")
    od.write_case_artifact(
        case_nodeid="t::a", filename="spectrum.html", content=b"y", kind="adi.iq"
    )
    manifest = od.finalize(run_meta={"plugin_version": "0.1.0"})
    assert manifest["schema_version"] == 2
    assert manifest["run_meta"] == {"plugin_version": "0.1.0"}
    assert any(a["kind"] == "dmesg_pre" for a in manifest["run_artifacts"])
    case = next(c for c in manifest["cases"] if c["case_nodeid"] == "t::a")
    art = case["artifacts"][0]
    assert art["kind"] == "adi.iq"
    assert art["rel_path"] == "cases/t__a/adi.iq/spectrum.html"
    on_disk = json.loads((root / "manifest.json").read_text())
    assert on_disk == manifest


def test_finalize_creates_run_meta_json(tmp_path: Path) -> None:
    root = tmp_path / "out"
    od = OutputDir(root)
    od.initialize()
    od.finalize(run_meta={"plugin_version": "0.1.0"})
    rm = json.loads((root / "run_meta.json").read_text())
    assert rm["plugin_version"] == "0.1.0"
