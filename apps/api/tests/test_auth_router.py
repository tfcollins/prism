"""Auth router integration tests."""
from fastapi.testclient import TestClient


def test_login_then_me(client: TestClient, seed_admin: None) -> None:
    r = client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    assert r.status_code == 200
    assert r.cookies.get("prism_session") is not None

    r2 = client.get("/api/v1/auth/me")
    assert r2.status_code == 200
    assert r2.json()["email"] == "admin@x.com"


def test_login_wrong_password(client: TestClient, seed_admin: None) -> None:
    r = client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "nope"})
    assert r.status_code == 401


def test_me_unauthenticated(client: TestClient) -> None:
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_logout_clears_cookie(client: TestClient, seed_admin: None) -> None:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    r = client.post("/api/v1/auth/logout")
    assert r.status_code == 204
    r2 = client.get("/api/v1/auth/me")
    assert r2.status_code == 401
