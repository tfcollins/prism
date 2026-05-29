"""API token router + bearer authentication."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from prism_api.repos.tokens import TokenRepo
from prism_api.repos.users import UserRepo
from prism_api.tokens import display_prefix, generate_token, hash_token


def _login(client: TestClient) -> str:
    r = client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    assert r.status_code == 200, r.text
    return client.cookies.get("prism_csrf") or ""


def test_create_list_revoke(client: TestClient, seed_admin: None) -> None:
    csrf = _login(client)
    created = client.post("/api/v1/tokens", json={"name": "ci"}, headers={"X-Prism-Csrf": csrf})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["token"].startswith("prism_")
    assert body["name"] == "ci"
    tid = body["id"]

    listed = client.get("/api/v1/tokens").json()
    assert [t["id"] for t in listed] == [tid]
    assert "token" not in listed[0]  # secret never returned again
    assert listed[0]["prefix"].startswith("prism_")

    revoked = client.delete(f"/api/v1/tokens/{tid}", headers={"X-Prism-Csrf": csrf})
    assert revoked.status_code == 204
    assert client.get("/api/v1/tokens").json() == []


def test_bearer_auth_works_and_skips_csrf(client: TestClient, seed_admin: None) -> None:
    csrf = _login(client)
    secret = client.post(
        "/api/v1/tokens", json={"name": "ci"}, headers={"X-Prism-Csrf": csrf}
    ).json()["token"]

    # Drop the session cookies so bearer is the only credential.
    client.cookies.clear()
    bearer = {"Authorization": f"Bearer {secret}"}

    me = client.get("/api/v1/auth/me", headers=bearer)
    assert me.status_code == 200
    assert me.json()["email"] == "admin@x.com"

    # A CSRF-protected POST (token create) with no CSRF header still works under bearer.
    again = client.post("/api/v1/tokens", json={"name": "ci2"}, headers=bearer)
    assert again.status_code == 201


def test_invalid_bearer_rejected(client: TestClient, seed_admin: None) -> None:
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer prism_not-a-real-token"})
    assert r.status_code == 401


def test_expired_token_rejected(client: TestClient, db_session: Session, seed_admin: None) -> None:
    user = UserRepo(db_session).get_by_email("admin@x.com")
    assert user is not None
    raw = generate_token()
    TokenRepo(db_session).create(
        user_id=user.id,
        name="old",
        token_hash=hash_token(raw),
        prefix=display_prefix(raw),
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    db_session.commit()
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {raw}"})
    assert r.status_code == 401


def test_tokens_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/tokens").status_code == 401
