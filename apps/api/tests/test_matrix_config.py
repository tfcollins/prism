"""MatrixConfig model + repo."""

from prism_api.models.matrix_config import MatrixConfig


def test_matrix_config_round_trips(db_session):
    db_session.add(MatrixConfig(scope="global", config={"stale_after_hours": 24}))
    db_session.flush()
    rows = db_session.query(MatrixConfig).all()
    assert rows[0].scope == "global"
    assert rows[0].config == {"stale_after_hours": 24}
