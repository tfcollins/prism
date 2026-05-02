"""Unit tests for entry-point loading, collision detection, and strict mode."""

from __future__ import annotations

from collections.abc import Mapping
from importlib.metadata import EntryPoint
from typing import Any
from unittest.mock import patch

import pytest

from pytest_prism.api import RenderContext, RenderResult, SessionContext
from pytest_prism.registry import RegistryError, load_registry


class _FakeRenderer:
    payload_kind = "fake.thing"

    def render(self, payload: Mapping[str, Any], ctx: RenderContext) -> RenderResult:
        return RenderResult()


class _FakeRendererB:
    payload_kind = "fake.thing"  # collides with _FakeRenderer

    def render(self, payload: Mapping[str, Any], ctx: RenderContext) -> RenderResult:
        return RenderResult()


class _FakeHook:
    name = "fake_hook"

    def session_pre(self, ctx: SessionContext) -> Mapping[str, Any]:
        return {}

    def session_post(self, ctx: SessionContext) -> Mapping[str, Any]:
        return {}


def _ep(group: str, name: str, target: type[object]) -> EntryPoint:
    """Build an EntryPoint that resolves to `target`."""
    ep = EntryPoint(name=name, value=f"{target.__module__}:{target.__name__}", group=group)
    return ep


def test_loads_renderers_from_entry_points() -> None:
    eps = [_ep("pytest_prism.renderers", "fake.thing", _FakeRenderer)]
    with patch("pytest_prism.registry._discover_entry_points", return_value=eps):
        reg = load_registry(strict=False)
    assert "fake.thing" in reg.renderers
    assert isinstance(reg.renderers["fake.thing"], _FakeRenderer)


def test_loads_session_hooks_from_entry_points() -> None:
    eps = [_ep("pytest_prism.session_hooks", "fake_hook", _FakeHook)]
    with patch("pytest_prism.registry._discover_entry_points", return_value=eps):
        reg = load_registry(strict=False)
    assert "fake_hook" in reg.session_hooks


def test_kind_collision_is_hard_error() -> None:
    eps = [
        _ep("pytest_prism.renderers", "fake.thing", _FakeRenderer),
        _ep("pytest_prism.renderers", "fake.thing", _FakeRendererB),
    ]
    with (
        patch("pytest_prism.registry._discover_entry_points", return_value=eps),
        pytest.raises(RegistryError, match=r"duplicate renderer kind 'fake\.thing'"),
    ):
        load_registry(strict=False)


def test_import_failure_skipped_by_default(caplog: pytest.LogCaptureFixture) -> None:
    bad = EntryPoint(name="broken", value="nonexistent_pkg:Thing", group="pytest_prism.renderers")
    eps = [bad]
    with patch("pytest_prism.registry._discover_entry_points", return_value=eps):
        reg = load_registry(strict=False)
    assert reg.renderers == {}
    assert "broken" in caplog.text


def test_import_failure_raises_in_strict_mode() -> None:
    bad = EntryPoint(name="broken", value="nonexistent_pkg:Thing", group="pytest_prism.renderers")
    with (
        patch("pytest_prism.registry._discover_entry_points", return_value=[bad]),
        pytest.raises(RegistryError, match="failed to import"),
    ):
        load_registry(strict=True)
