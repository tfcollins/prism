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
