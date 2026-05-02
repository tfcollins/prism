"""Verify the plugin is a strict no-op when --prism-report is not passed."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

# Arguments forwarded to every inner pytest invocation to keep it stable
# regardless of what globally-installed plugins are registered in the outer
# process.  We disable every plugin that either (a) conflicts when re-entered
# in-process (labgrid StepLogger is a singleton), (b) emits deprecation
# warnings that the parent's filterwarnings=error would promote to errors, or
# (c) is simply irrelevant for these lifecycle tests.
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


def test_plugin_inert_when_flag_off(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("""
        def test_passes():
            assert True
    """)
    result = pytester.runpytest_inprocess("-q", *_DISABLE_NOISY_PLUGINS)
    result.assert_outcomes(passed=1)
    assert not list(pytester.path.glob("prism-report-*"))
    assert "pytest-prism" not in result.stdout.str()


def test_plugin_creates_out_dir_when_flag_on(pytester: pytest.Pytester, tmp_path: Path) -> None:
    out = tmp_path / "out"
    pytester.makepyfile("""
        def test_passes():
            assert True
    """)
    result = pytester.runpytest_inprocess(
        "-q", "--prism-report", f"--prism-out={out}", *_DISABLE_NOISY_PLUGINS
    )
    result.assert_outcomes(passed=1)
    assert (out / "manifest.json").exists()
    assert (out / "run_meta.json").exists()
    assert (out / "junit.xml").exists()
