from fastapi.testclient import TestClient


def _login(client: TestClient) -> str:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    return client.cookies.get("prism_csrf") or ""


def test_mask_crud(client: TestClient, seed_admin) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "rf", "name": "RF"})

    # Empty to start
    assert client.get("/api/v1/projects/rf/masks").json() == []

    # Create
    body = {
        "name": "SEM 2.4GHz",
        "segments": [
            {"f_start": 2.30e9, "f_end": 2.39e9, "max_dbm": -40.0},
            {"f_start": 2.39e9, "f_end": 2.41e9, "max_dbm": 0.0},
            {"f_start": 2.41e9, "f_end": 2.50e9, "max_dbm": -40.0},
        ],
    }
    resp = client.post("/api/v1/projects/rf/masks", json=body, headers={"X-Prism-Csrf": csrf})
    assert resp.status_code == 201, resp.text
    mask = resp.json()
    assert mask["name"] == "SEM 2.4GHz"
    assert len(mask["segments"]) == 3
    assert mask["segments"][1]["max_dbm"] == 0.0
    mask_id = mask["id"]

    # List
    masks = client.get("/api/v1/projects/rf/masks").json()
    assert [m["id"] for m in masks] == [mask_id]

    # Delete
    d = client.delete(f"/api/v1/projects/rf/masks/{mask_id}", headers={"X-Prism-Csrf": csrf})
    assert d.status_code == 204
    assert client.get("/api/v1/projects/rf/masks").json() == []


def test_mask_create_requires_segments(client: TestClient, seed_admin) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "rf", "name": "RF"})
    resp = client.post(
        "/api/v1/projects/rf/masks",
        json={"name": "empty", "segments": []},
        headers={"X-Prism-Csrf": csrf},
    )
    assert resp.status_code == 422


def test_mask_unknown_project_404(client: TestClient, seed_admin) -> None:
    _login(client)
    assert client.get("/api/v1/projects/nope/masks").status_code == 404
