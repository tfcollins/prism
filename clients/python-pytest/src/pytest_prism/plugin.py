"""Pytest plugin entry. Real wiring lands in Task 8."""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    g = parser.getgroup("prism_report", "Prism test-report plugin")
    g.addoption("--prism-report", action="store_true", default=False)


def pytest_configure(config: pytest.Config) -> None:
    if not config.getoption("--prism-report"):
        return
