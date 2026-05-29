"""Integration tests for LDAP login via the auth router (with local fallback)."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from prism_api.config import Settings
from prism_api.deps import get_settings_dep, session_dep
from prism_api.main import app
from prism_api.repos.users import UserRepo

DIRECTORY = [
    (
        "uid=alice,ou=people,dc=example,dc=com",
        {
            "objectClass": ["inetOrgPerson", "top"],
            "uid": "alice",
            "mail": "alice@example.com",
            "userPassword": "s3cret",
        },
    ),
]


@pytest.fixture
def ldap_settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        database_url="sqlite:///:memory:",
        s3_endpoint="x",
        s3_access_key="x",
        s3_secret_key="x",
        s3_bucket="x",
        redis_url="x",
        jwt_secret="testsecretlongenough",
        ldap_enabled=True,
        ldap_server="ldap://mock",
        ldap_user_base_dn="ou=people,dc=example,dc=com",
        ldap_user_filter="(mail={email})",
    )


@pytest.fixture
def ldap_client(
    ldap_settings: Settings,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    mock_ldap_connect,
) -> Iterator[TestClient]:
    monkeypatch.setattr("prism_api.ldap_auth.connect", mock_ldap_connect(DIRECTORY))
    app.dependency_overrides[get_settings_dep] = lambda: ldap_settings
    app.dependency_overrides[session_dep] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_ldap_login_provisions_user_and_me(ldap_client: TestClient, db_session: Session) -> None:
    resp = ldap_client.post(
        "/api/v1/auth/login", json={"email": "alice@example.com", "password": "s3cret"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["auth_provider"] == "ldap"

    # /me works with the issued session cookie.
    me = ldap_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"
    assert me.json()["auth_provider"] == "ldap"

    # The user was just-in-time provisioned with no local password.
    user = UserRepo(db_session).get_by_email("alice@example.com")
    assert user is not None
    assert user.auth_provider == "ldap"
    assert user.password_hash is None


def test_ldap_login_wrong_password(ldap_client: TestClient) -> None:
    resp = ldap_client.post(
        "/api/v1/auth/login", json={"email": "alice@example.com", "password": "nope"}
    )
    assert resp.status_code == 401


def test_local_admin_still_logs_in_with_ldap_enabled(
    ldap_client: TestClient, seed_admin: None
) -> None:
    # The bootstrap admin is a local account; it must authenticate locally even
    # though LDAP is enabled (and the mock directory has no such user).
    resp = ldap_client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["auth_provider"] == "local"


def test_unknown_user_rejected_when_ldap_disabled(client: TestClient) -> None:
    # Default client fixture has LDAP disabled.
    resp = client.post(
        "/api/v1/auth/login", json={"email": "ghost@example.com", "password": "whatever"}
    )
    assert resp.status_code == 401
