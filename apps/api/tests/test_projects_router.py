"""Projects router tests."""

from fastapi.testclient import TestClient


def _login(client: TestClient) -> None:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})


def test_create_list_get(client: TestClient, seed_admin: None) -> None:
    _login(client)
    r = client.post(
        "/api/v1/projects",
        json={"slug": "audio-codec", "name": "Audio Codec", "description": "DSP work"},
    )
    assert r.status_code == 201
    listing = client.get("/api/v1/projects").json()
    assert listing[0]["slug"] == "audio-codec"

    detail = client.get("/api/v1/projects/audio-codec").json()
    assert detail["name"] == "Audio Codec"


def test_get_unknown_404(client: TestClient, seed_admin: None) -> None:
    _login(client)
    r = client.get("/api/v1/projects/missing")
    assert r.status_code == 404


def test_create_duplicate_409(client: TestClient, seed_admin: None) -> None:
    _login(client)
    client.post(
        "/api/v1/projects",
        json={"slug": "a", "name": "A"},
    )
    r = client.post("/api/v1/projects", json={"slug": "a", "name": "A2"})
    assert r.status_code == 409


def test_invalid_slug_422(client: TestClient, seed_admin: None) -> None:
    _login(client)
    r = client.post("/api/v1/projects", json={"slug": "Has Spaces", "name": "x"})
    assert r.status_code == 422
