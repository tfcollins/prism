from fastapi.testclient import TestClient


def _login(client: TestClient) -> str:
    client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw"})
    return client.cookies.get("prism_csrf") or ""


def test_saved_view_crud(client: TestClient, seed_admin) -> None:
    csrf = _login(client)
    client.post("/api/v1/projects", json={"slug": "rf", "name": "RF"})

    cfg = {"tab": "trends", "measurement": "channel_power_dBm", "tagFilters": {"dut": "A"}}
    r = client.put(
        "/api/v1/projects/rf/views",
        json={"name": "default", "config": cfg},
        headers={"X-Prism-Csrf": csrf},
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"name": "default", "config": cfg}

    # upsert overwrites config for the same name
    cfg2 = {"tab": "runs", "tagFilters": {}}
    client.put(
        "/api/v1/projects/rf/views",
        json={"name": "default", "config": cfg2},
        headers={"X-Prism-Csrf": csrf},
    )
    views = client.get("/api/v1/projects/rf/views").json()
    assert views == [{"name": "default", "config": cfg2}]

    d = client.delete("/api/v1/projects/rf/views/default", headers={"X-Prism-Csrf": csrf})
    assert d.status_code == 204
    assert client.get("/api/v1/projects/rf/views").json() == []


def test_view_requires_csrf(client: TestClient, seed_admin) -> None:
    _login(client)
    client.post("/api/v1/projects", json={"slug": "rf", "name": "RF"})
    r = client.put("/api/v1/projects/rf/views", json={"name": "x", "config": {}})
    assert r.status_code == 403
