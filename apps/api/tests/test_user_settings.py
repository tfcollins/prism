"""UserSetting model + repo."""

from prism_api.models.user_settings import UserSetting
from prism_api.repos.user_settings import UserSettingsRepo


def test_user_setting_round_trips_json(db_session):
    db_session.add(UserSetting(user_id="u1", key="matrix_dashboard", value={"enabled": True}))
    db_session.flush()
    got = db_session.get(UserSetting, ("u1", "matrix_dashboard"))
    assert got is not None
    assert got.value == {"enabled": True}


def test_repo_get_missing_returns_none(db_session):
    assert UserSettingsRepo(db_session).get("nobody", "matrix_dashboard") is None


def test_repo_upsert_inserts_then_updates(db_session):
    repo = UserSettingsRepo(db_session)
    repo.upsert("u1", "matrix_dashboard", {"enabled": False})
    db_session.flush()
    repo.upsert("u1", "matrix_dashboard", {"enabled": True, "rotate": True})
    db_session.flush()
    got = repo.get("u1", "matrix_dashboard")
    assert got is not None
    assert got.value == {"enabled": True, "rotate": True}
