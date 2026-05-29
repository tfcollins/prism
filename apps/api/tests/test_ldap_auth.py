"""Unit tests for the LDAP search+bind logic (ldap3 MOCK_SYNC backed)."""

import pytest

from prism_api import ldap_auth
from prism_api.config import Settings

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


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "database_url": "sqlite:///:memory:",
        "s3_endpoint": "x",
        "s3_access_key": "x",
        "s3_secret_key": "x",
        "s3_bucket": "x",
        "redis_url": "x",
        "jwt_secret": "testsecretlongenough",
        "ldap_enabled": True,
        "ldap_server": "ldap://mock",
        "ldap_user_base_dn": "ou=people,dc=example,dc=com",
        "ldap_user_filter": "(mail={email})",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_authenticate_success(monkeypatch: pytest.MonkeyPatch, mock_ldap_connect) -> None:
    monkeypatch.setattr(ldap_auth, "connect", mock_ldap_connect(DIRECTORY))
    identity = ldap_auth.ldap_authenticate("alice@example.com", "s3cret", _settings())
    assert identity is not None
    assert identity.dn == "uid=alice,ou=people,dc=example,dc=com"
    assert identity.email == "alice@example.com"


def test_authenticate_wrong_password(monkeypatch: pytest.MonkeyPatch, mock_ldap_connect) -> None:
    monkeypatch.setattr(ldap_auth, "connect", mock_ldap_connect(DIRECTORY))
    assert ldap_auth.ldap_authenticate("alice@example.com", "wrong", _settings()) is None


def test_authenticate_user_not_found(monkeypatch: pytest.MonkeyPatch, mock_ldap_connect) -> None:
    monkeypatch.setattr(ldap_auth, "connect", mock_ldap_connect(DIRECTORY))
    assert ldap_auth.ldap_authenticate("nobody@example.com", "s3cret", _settings()) is None


def test_empty_password_rejected_without_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # connect must never be called for an empty password (anonymous-bind bypass).
    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("connect() should not be called for an empty password")

    monkeypatch.setattr(ldap_auth, "connect", _boom)
    assert ldap_auth.ldap_authenticate("alice@example.com", "", _settings()) is None


def test_username_filter_template(monkeypatch: pytest.MonkeyPatch, mock_ldap_connect) -> None:
    # Filter using {username} (local part) instead of {email}.
    monkeypatch.setattr(ldap_auth, "connect", mock_ldap_connect(DIRECTORY))
    identity = ldap_auth.ldap_authenticate(
        "alice@example.com", "s3cret", _settings(ldap_user_filter="(uid={username})")
    )
    assert identity is not None
    assert identity.dn == "uid=alice,ou=people,dc=example,dc=com"


def test_missing_server_returns_none(monkeypatch: pytest.MonkeyPatch, mock_ldap_connect) -> None:
    # No server/base configured (e.g. enabled flag off elsewhere) -> no auth.
    monkeypatch.setattr(ldap_auth, "connect", mock_ldap_connect(DIRECTORY))
    s = _settings()
    object.__setattr__(s, "ldap_server", None)
    assert ldap_auth.ldap_authenticate("alice@example.com", "s3cret", s) is None
