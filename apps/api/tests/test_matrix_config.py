"""MatrixConfig model + repo."""

from prism_api.models.matrix_config import MatrixConfig
from prism_api.repos.matrix_config import DEFAULT_MATRIX_CONFIG, MatrixConfigRepo


def test_matrix_config_round_trips(db_session):
    db_session.add(MatrixConfig(scope="global", config={"stale_after_hours": 24}))
    db_session.flush()
    rows = db_session.query(MatrixConfig).all()
    assert rows[0].scope == "global"
    assert rows[0].config == {"stale_after_hours": 24}


def test_effective_returns_defaults_when_absent(db_session):
    eff = MatrixConfigRepo(db_session).effective("global")
    assert eff == DEFAULT_MATRIX_CONFIG


def test_effective_merges_overrides_over_defaults(db_session):
    repo = MatrixConfigRepo(db_session)
    repo.upsert("global", {"stale_after_hours": 24, "curated_rows": ["ad9152"]})
    db_session.flush()
    eff = repo.effective("global")
    assert eff["stale_after_hours"] == 24
    assert eff["curated_rows"] == ["ad9152"]
    # untouched keys fall back to defaults
    assert eff["row_key"] == DEFAULT_MATRIX_CONFIG["row_key"]
    assert eff["refresh_seconds"] == DEFAULT_MATRIX_CONFIG["refresh_seconds"]
