"""Users router tests."""

from fastapi.testclient import TestClient


def _login(client: TestClient, email: str = "admin@x.com", password: str = "pw") -> None:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200


def test_list_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/users").status_code == 401


def test_create_and_list(client: TestClient, seed_admin: None) -> None:
    _login(client)
    r = client.post(
        "/api/v1/users",
        json={"email": "newbie@x.com", "password": "anotherpw"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "newbie@x.com"

    listing = client.get("/api/v1/users").json()
    assert {u["email"] for u in listing} == {"admin@x.com", "newbie@x.com"}


def test_create_duplicate_email(client: TestClient, seed_admin: None) -> None:
    _login(client)
    r = client.post(
        "/api/v1/users",
        json={"email": "admin@x.com", "password": "longpw2!!"},
    )
    assert r.status_code == 409


def test_delete_user(client: TestClient, seed_admin: None) -> None:
    _login(client)
    new = client.post(
        "/api/v1/users",
        json={"email": "victim@x.com", "password": "longpw!!!"},
    ).json()
    r = client.delete(f"/api/v1/users/{new['id']}")
    assert r.status_code == 204
    assert {u["email"] for u in client.get("/api/v1/users").json()} == {"admin@x.com"}


def test_cannot_delete_self(client: TestClient, seed_admin: None) -> None:
    _login(client)
    me = client.get("/api/v1/auth/me").json()
    r = client.delete(f"/api/v1/users/{me['id']}")
    assert r.status_code == 400
    assert "self" in r.json()["detail"].lower()


def test_cannot_delete_last_user(client: TestClient, seed_admin: None) -> None:
    _login(client)
    me = client.get("/api/v1/auth/me").json()
    # Create a second user
    second = client.post(
        "/api/v1/users", json={"email": "other@x.com", "password": "longpw!!"}
    ).json()
    # Log in as the second user
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"email": "other@x.com", "password": "longpw!!"})
    # Delete admin (the only other user) — should succeed, leaving just `second`
    r = client.delete(f"/api/v1/users/{me['id']}")
    assert r.status_code == 204
    # Now `second` is the only user; trying to delete itself is blocked (self-guard wins)
    r2 = client.delete(f"/api/v1/users/{second['id']}")
    assert r2.status_code == 400


def test_delete_unknown_user_404(client: TestClient, seed_admin: None) -> None:
    _login(client)
    r = client.delete("/api/v1/users/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
