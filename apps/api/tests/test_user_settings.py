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
    repo.upsert("u1", "matrix_dashboard", {"enabled": True, "rotate": True})
    got = repo.get("u1", "matrix_dashboard")
    assert got is not None
    assert got.value == {"enabled": True, "rotate": True}


def _login(client, db_session, settings):
    from prism_api.auth import hash_password
    from prism_api.repos.users import UserRepo

    UserRepo(db_session).create(
        email=settings.admin_email or "admin@x.com", password_hash=hash_password("pw")
    )
    db_session.commit()
    r = client.post(
        "/api/v1/auth/login",
        json={"email": settings.admin_email or "admin@x.com", "password": "pw"},
    )
    assert r.status_code == 200


def test_get_missing_setting_returns_404(client, db_session, settings):
    _login(client, db_session, settings)
    r = client.get("/api/v1/me/settings/matrix_dashboard")
    assert r.status_code == 404


def test_put_then_get_setting(client, db_session, settings):
    _login(client, db_session, settings)
    csrf = client.cookies.get("prism_csrf")
    r = client.put(
        "/api/v1/me/settings/matrix_dashboard",
        json={"value": {"enabled": True, "rotate": False}},
        headers={"X-Prism-Csrf": csrf},
    )
    assert r.status_code == 200
    assert r.json()["value"] == {"enabled": True, "rotate": False}
    r2 = client.get("/api/v1/me/settings/matrix_dashboard")
    assert r2.status_code == 200
    assert r2.json()["value"]["enabled"] is True


def test_put_requires_csrf(client, db_session, settings):
    _login(client, db_session, settings)
    r = client.put("/api/v1/me/settings/matrix_dashboard", json={"value": {"enabled": True}})
    assert r.status_code == 403
