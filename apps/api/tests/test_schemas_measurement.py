import pytest

from prism_api.schemas.case import measurement_margin


def test_margin_none_without_limits() -> None:
    assert measurement_margin(1.0, None, None) is None


def test_margin_max_only() -> None:
    assert measurement_margin(-10.0, None, -9.0) == pytest.approx(1.0)  # inside
    assert measurement_margin(-8.0, None, -9.0) == pytest.approx(-1.0)  # over ceiling


def test_margin_min_only() -> None:
    assert measurement_margin(5.0, 3.0, None) == pytest.approx(2.0)  # inside
    assert measurement_margin(2.0, 3.0, None) == pytest.approx(-1.0)  # under floor


def test_margin_both_limits_returns_nearest() -> None:
    # window [3, 9], value 8 → 1 to ceiling, 5 to floor → nearest is 1
    assert measurement_margin(8.0, 3.0, 9.0) == pytest.approx(1.0)
