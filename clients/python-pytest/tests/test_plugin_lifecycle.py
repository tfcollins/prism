"""Verify per-test renderer dispatch via attach() + a registered fake renderer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

# Disable every globally-installed plugin that either conflicts in in-process
# re-entry (labgrid's StepLogger singleton) or emits PytestDeprecationWarnings
# that the outer filterwarnings=error config would escalate to errors.
_DISABLE_NOISY_PLUGINS = [
    "-p",
    "no:labgrid",
    "-p",
    "no:asyncio",
    "-p",
    "no:reporter",
    "-p",
    "no:html",
    "-p",
    "no:metadata",
    "-p",
    "no:dotenv",
    "-p",
    "no:libiio",
    "-p",
    "no:genalyzer",
    "-p",
    "no:xdist",
]


def test_attach_with_no_registered_renderer_falls_through(
    pytester: pytest.Pytester, tmp_path: Path
) -> None:
    """Payload of an unknown kind is dumped as raw.json with a warning."""
    out = tmp_path / "out"
    pytester.makepyfile("""
        from pytest_prism import attach
        def test_attach_unknown_kind():
            attach("does.not.exist", {"x": 1, "y": "hi"})
            assert True
    """)
    result = pytester.runpytest_inprocess(
        "-q", "--prism-report", f"--prism-out={out}", *_DISABLE_NOISY_PLUGINS
    )
    result.assert_outcomes(passed=1)
    raw = list((out / "cases").rglob("does.not.exist/raw.json"))
    assert len(raw) == 1, f"expected 1 raw.json, found {raw}"
    payload = json.loads(raw[0].read_text())
    assert payload == {"x": 1, "y": "hi"}


def test_strict_registry_rejects_bad_entry_point(
    pytester: pytest.Pytester, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """In strict mode, an entry point that fails to import → UsageError."""
    from importlib.metadata import EntryPoint

    bad = EntryPoint(
        name="broken",
        value="nonexistent_pkg:Thing",
        group="pytest_prism.renderers",
    )
    monkeypatch.setattr("pytest_prism.registry._discover_entry_points", lambda: [bad])
    pytester.makepyfile("def test_a(): assert True")
    result = pytester.runpytest_inprocess(
        "-q",
        "--prism-report",
        f"--prism-out={tmp_path / 'out'}",
        "--prism-strict-registry",
        *_DISABLE_NOISY_PLUGINS,
    )
    assert result.ret != 0
    assert "failed to import" in result.stderr.str() + result.stdout.str()


def test_out_dir_overwrite_flag_clears_existing(pytester: pytest.Pytester, tmp_path: Path) -> None:
    """--prism-out-overwrite removes the dir before writing."""
    out = tmp_path / "out"
    out.mkdir()
    (out / "stale.txt").write_text("old")
    pytester.makepyfile("def test_a(): assert True")
    result = pytester.runpytest_inprocess(
        "-q",
        "--prism-report",
        f"--prism-out={out}",
        "--prism-out-overwrite",
        *_DISABLE_NOISY_PLUGINS,
    )
    result.assert_outcomes(passed=1)
    assert not (out / "stale.txt").exists()
    assert (out / "manifest.json").exists()
