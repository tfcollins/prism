"""L3: fake renderer + fake hook end-to-end via monkeypatched entry points."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from importlib.metadata import EntryPoint
from pathlib import Path
from typing import Any

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


# --- module-level fakes so EntryPoint.load() can resolve them ---
class _SentinelRenderer:
    payload_kind = "sentinel.kind"

    def render(self, payload: Mapping[str, Any], ctx: Any) -> Any:
        from pytest_prism import RenderResult

        (ctx.case_dir / "sentinel.txt").write_text(f"got {payload['x']}")
        return RenderResult(
            files=[(ctx.case_dir / "sentinel.txt").relative_to(ctx.case_dir)],
            metrics={"value": float(payload["x"])},
            primary_artifact="sentinel.txt",
        )


class _SentinelHook:
    name = "sentinel_hook"

    def session_pre(self, ctx: Any) -> Mapping[str, Any]:
        (ctx.hook_dir / "pre.txt").write_text("hello pre")
        return {"phase": "pre"}

    def session_post(self, ctx: Any) -> Mapping[str, Any]:
        (ctx.hook_dir / "post.txt").write_text("hello post")
        return {"phase": "post"}


@pytest.fixture
def patched_entry_points(monkeypatch: pytest.MonkeyPatch) -> None:
    eps = [
        EntryPoint(
            name="sentinel.kind",
            value=f"{__name__}:_SentinelRenderer",
            group="pytest_prism.renderers",
        ),
        EntryPoint(
            name="sentinel_hook",
            value=f"{__name__}:_SentinelHook",
            group="pytest_prism.session_hooks",
        ),
    ]
    monkeypatch.setattr("pytest_prism.registry._discover_entry_points", lambda: eps)


def test_renderer_dispatch_writes_to_per_kind_subdir(
    pytester: pytest.Pytester,
    tmp_path: Path,
    patched_entry_points: None,
) -> None:
    out = tmp_path / "out"
    pytester.makepyfile("""
        from pytest_prism import attach
        def test_a():
            attach("sentinel.kind", {"x": 42})
    """)
    result = pytester.runpytest_inprocess(
        "-q", "--prism-report", f"--prism-out={out}", *_DISABLE_NOISY_PLUGINS
    )
    result.assert_outcomes(passed=1)

    sentinel_files = list((out / "cases").rglob("sentinel.kind/sentinel.txt"))
    assert len(sentinel_files) == 1
    assert sentinel_files[0].read_text() == "got 42"

    metrics_files = list((out / "cases").rglob("sentinel.kind/metrics.json"))
    assert len(metrics_files) == 1
    assert json.loads(metrics_files[0].read_text())["value"] == 42.0


def test_session_hook_runs_pre_and_post(
    pytester: pytest.Pytester,
    tmp_path: Path,
    patched_entry_points: None,
) -> None:
    out = tmp_path / "out"
    pytester.makepyfile("def test_a(): assert True")
    result = pytester.runpytest_inprocess(
        "-q", "--prism-report", f"--prism-out={out}", *_DISABLE_NOISY_PLUGINS
    )
    result.assert_outcomes(passed=1)
    assert (out / "session" / "sentinel_hook" / "pre.txt").read_text() == "hello pre"
    assert (out / "session" / "sentinel_hook" / "post.txt").read_text() == "hello post"
    rm = json.loads((out / "run_meta.json").read_text())
    assert rm["session_pre"]["sentinel_hook"]["phase"] == "pre"
    assert rm["session_post"]["sentinel_hook"]["phase"] == "post"


def test_renderer_exception_writes_error_log_and_does_not_fail_test(
    pytester: pytest.Pytester,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Boom:
        payload_kind = "boom"

        def render(self, payload: Mapping[str, Any], ctx: Any) -> Any:
            raise RuntimeError("kaboom")

    sys.modules[__name__]._Boom = _Boom  # type: ignore[attr-defined]

    eps = [
        EntryPoint(
            name="boom",
            value=f"{__name__}:_Boom",
            group="pytest_prism.renderers",
        )
    ]
    monkeypatch.setattr("pytest_prism.registry._discover_entry_points", lambda: eps)

    out = tmp_path / "out"
    pytester.makepyfile("""
        from pytest_prism import attach
        def test_a(): attach("boom", {})
    """)
    result = pytester.runpytest_inprocess(
        "-q", "--prism-report", f"--prism-out={out}", *_DISABLE_NOISY_PLUGINS
    )
    result.assert_outcomes(passed=1)
    err_files = list((out / "cases").rglob("boom/error.log"))
    assert len(err_files) == 1
    assert "kaboom" in err_files[0].read_text()


def test_two_attaches_two_subdirs(
    pytester: pytest.Pytester,
    tmp_path: Path,
    patched_entry_points: None,
) -> None:
    """A single test that attaches two kinds gets two subdirs under cases/<id>/."""

    class _Other:
        payload_kind = "other.kind"

        def render(self, payload: Mapping[str, Any], ctx: Any) -> Any:
            from pytest_prism import RenderResult

            (ctx.case_dir / "o.txt").write_text("other")
            return RenderResult(files=[(ctx.case_dir / "o.txt").relative_to(ctx.case_dir)])

    sys.modules[__name__]._Other = _Other  # type: ignore[attr-defined]

    out = tmp_path / "out"
    pytester.makepyfile("""
        from pytest_prism import attach
        def test_a():
            attach("sentinel.kind", {"x": 1})
            attach("other.kind", {})
    """)

    eps = [
        EntryPoint(
            name="sentinel.kind",
            value=f"{__name__}:_SentinelRenderer",
            group="pytest_prism.renderers",
        ),
        EntryPoint(
            name="other.kind",
            value=f"{__name__}:_Other",
            group="pytest_prism.renderers",
        ),
    ]
    import pytest_prism.registry as _r

    _orig = _r._discover_entry_points
    _r._discover_entry_points = lambda: eps
    try:
        result = pytester.runpytest_inprocess(
            "-q", "--prism-report", f"--prism-out={out}", *_DISABLE_NOISY_PLUGINS
        )
    finally:
        _r._discover_entry_points = _orig

    result.assert_outcomes(passed=1)
    assert list((out / "cases").rglob("sentinel.kind/sentinel.txt"))
    assert list((out / "cases").rglob("other.kind/o.txt"))
