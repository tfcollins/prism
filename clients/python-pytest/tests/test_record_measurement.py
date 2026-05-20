"""Tests for the record_measurement() helper."""

from __future__ import annotations

import pytest

from pytest_prism import api, record_measurement

pytest_plugins = ["pytester"]


class _FakeItem:
    def __init__(self) -> None:
        self.user_properties: list[tuple[str, object]] = []


def test_appends_value_unit_and_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    item = _FakeItem()
    monkeypatch.setattr(api, "_current_item", lambda: item)
    record_measurement("channel_power_dBm", -10.2, unit="dBm", spec_max=-9.0)
    props = item.user_properties
    assert ("channel_power_dBm", -10.2) in props
    assert ("channel_power_dBm__unit", "dBm") in props
    assert ("channel_power_dBm__max", -9.0) in props
    # spec_min was not provided -> no __min property
    assert all(not k.endswith("__min") for k, _ in props)


def test_noop_outside_a_test(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_current_item", lambda: None)
    record_measurement("x", 1.0)  # must not raise


def test_lands_in_junit_xml(pytester: pytest.Pytester) -> None:
    """End-to-end: the recorded values appear as <property> in pytest's JUnit."""
    pytester.makepyfile(
        """
        from pytest_prism import record_measurement

        def test_rf():
            record_measurement("acpr_dBc", -45.3, unit="dBc", spec_max=-40.0)
        """
    )
    xml = pytester.path / "out.xml"
    result = pytester.runpytest("--junitxml", str(xml))
    result.assert_outcomes(passed=1)
    content = xml.read_text()
    assert 'name="acpr_dBc" value="-45.3"' in content
    assert 'name="acpr_dBc__unit" value="dBc"' in content
    assert 'name="acpr_dBc__max" value="-40.0"' in content
