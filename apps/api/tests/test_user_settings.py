"""UserSetting model + repo."""

from prism_api.models.user_settings import UserSetting


def test_user_setting_round_trips_json(db_session):
    db_session.add(UserSetting(user_id="u1", key="matrix_dashboard", value={"enabled": True}))
    db_session.flush()
    got = db_session.get(UserSetting, ("u1", "matrix_dashboard"))
    assert got is not None
    assert got.value == {"enabled": True}
