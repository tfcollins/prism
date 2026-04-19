"""Database engine + session smoke tests (uses SQLite in-memory)."""
from sqlalchemy import text

from prism_api.db import build_engine, build_session_factory


def test_engine_round_trip() -> None:
    engine = build_engine("sqlite:///:memory:")
    session_factory = build_session_factory(engine)
    with session_factory() as session:
        result = session.execute(text("SELECT 1")).scalar_one()
        assert result == 1
