from prism_api.schemas.spec import resolve_spec


def test_project_spec_fills_gaps_when_no_embedded_limits() -> None:
    assert resolve_spec(None, None, 1.0, 5.0) == (1.0, 5.0)


def test_embedded_limits_win_over_project_spec() -> None:
    # any embedded limit (even just one side) freezes the pair; project ignored
    assert resolve_spec(None, 4.0, 1.0, 99.0) == (None, 4.0)
    assert resolve_spec(2.0, None, 0.0, 99.0) == (2.0, None)
    assert resolve_spec(2.0, 4.0, 0.0, 99.0) == (2.0, 4.0)


def test_no_limits_anywhere() -> None:
    assert resolve_spec(None, None, None, None) == (None, None)
