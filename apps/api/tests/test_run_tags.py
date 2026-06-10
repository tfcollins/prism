"""Run tag editing — repo methods + HTTP endpoints."""

from prism_api.auth import hash_password
from prism_api.models.project import Project
from prism_api.models.run import RunStatus, TestRun
from prism_api.repos.audit import AuditRepo
from prism_api.repos.runs import RunRepo
from prism_api.repos.users import UserRepo


def _run(db_session) -> TestRun:
    p = Project(slug="proj", name="Proj")
    db_session.add(p)
    db_session.flush()
    run = TestRun(project_id=p.id, name="r", status=RunStatus.PASS)
    db_session.add(run)
    db_session.flush()
    return run


def test_get_tag_missing_returns_none(db_session):
    run = _run(db_session)
    assert RunRepo(db_session).get_tag(run.id, "hw") is None


def test_create_then_get_tag(db_session):
    run = _run(db_session)
    repo = RunRepo(db_session)
    repo.create_tag(run.id, "hw", "ad9081")
    got = repo.get_tag(run.id, "hw")
    assert got is not None
    assert got.value == "ad9081"


def test_update_tag_changes_value(db_session):
    run = _run(db_session)
    repo = RunRepo(db_session)
    repo.create_tag(run.id, "hw", "ad9081")
    repo.update_tag(run.id, "hw", "adrv9009")
    assert repo.get_tag(run.id, "hw").value == "adrv9009"


def test_delete_tag_removes_and_reports(db_session):
    run = _run(db_session)
    repo = RunRepo(db_session)
    repo.create_tag(run.id, "hw", "ad9081")
    assert repo.delete_tag(run.id, "hw") is True
    assert repo.get_tag(run.id, "hw") is None
    assert repo.delete_tag(run.id, "hw") is False


def _latest_event(db_session, project_id, action):
    evs = [e for e in AuditRepo(db_session).list_for_project(project_id) if e.action == action]
    assert evs, f"no {action} event recorded"
    return evs[0]  # list_for_project returns newest first


def _login(client, db_session):
    UserRepo(db_session).create(email="u@x.com", password_hash=hash_password("pw"))
    db_session.commit()
    r = client.post("/api/v1/auth/login", json={"email": "u@x.com", "password": "pw"})
    assert r.status_code == 200


def _seed_run(db_session) -> str:
    run = _run(db_session)
    db_session.commit()
    return run.id


def test_add_tag_requires_auth(client, db_session):
    rid = _seed_run(db_session)
    r = client.post(f"/api/v1/runs/{rid}/tags", json={"key": "hw", "value": "x"})
    assert r.status_code == 401


def test_add_tag_requires_csrf(client, db_session):
    _login(client, db_session)
    rid = _seed_run(db_session)
    r = client.post(f"/api/v1/runs/{rid}/tags", json={"key": "hw", "value": "x"})
    assert r.status_code == 403


def test_add_tag_creates(client, db_session):
    _login(client, db_session)
    rid = _seed_run(db_session)
    csrf = client.cookies.get("prism_csrf")
    r = client.post(
        f"/api/v1/runs/{rid}/tags",
        json={"key": "hw", "value": "ad9081"},
        headers={"X-Prism-Csrf": csrf},
    )
    assert r.status_code == 201
    assert r.json() == {"key": "hw", "value": "ad9081"}
    assert RunRepo(db_session).get_tag(rid, "hw").value == "ad9081"
    events = [
        e.action
        for e in AuditRepo(db_session).list_for_project(db_session.get(TestRun, rid).project_id)
    ]
    assert "run.tag.add" in events
    ev = _latest_event(db_session, db_session.get(TestRun, rid).project_id, "run.tag.add")
    assert ev.detail == {"key": "hw", "value": "ad9081"}


def test_add_duplicate_key_conflicts(client, db_session):
    _login(client, db_session)
    rid = _seed_run(db_session)
    csrf = client.cookies.get("prism_csrf")
    h = {"X-Prism-Csrf": csrf}
    client.post(f"/api/v1/runs/{rid}/tags", json={"key": "hw", "value": "a"}, headers=h)
    r = client.post(f"/api/v1/runs/{rid}/tags", json={"key": "hw", "value": "b"}, headers=h)
    assert r.status_code == 409


def test_add_tag_unknown_run_404(client, db_session):
    _login(client, db_session)
    csrf = client.cookies.get("prism_csrf")
    r = client.post(
        "/api/v1/runs/nope/tags",
        json={"key": "hw", "value": "a"},
        headers={"X-Prism-Csrf": csrf},
    )
    assert r.status_code == 404


def test_add_tag_validation(client, db_session):
    _login(client, db_session)
    rid = _seed_run(db_session)
    csrf = client.cookies.get("prism_csrf")
    h = {"X-Prism-Csrf": csrf}
    r1 = client.post(f"/api/v1/runs/{rid}/tags", json={"key": "", "value": "a"}, headers=h)
    assert r1.status_code == 422
    r2 = client.post(f"/api/v1/runs/{rid}/tags", json={"key": "k", "value": "  "}, headers=h)
    assert r2.status_code == 422
    r3 = client.post(f"/api/v1/runs/{rid}/tags", json={"key": "k" * 101, "value": "a"}, headers=h)
    assert r3.status_code == 422


def test_update_tag_requires_auth(client, db_session):
    rid = _seed_run(db_session)
    assert client.put(f"/api/v1/runs/{rid}/tags/hw", json={"value": "b"}).status_code == 401


def test_update_tag_requires_csrf(client, db_session):
    _login(client, db_session)
    rid = _seed_run(db_session)
    assert client.put(f"/api/v1/runs/{rid}/tags/hw", json={"value": "b"}).status_code == 403


def test_delete_tag_requires_auth(client, db_session):
    rid = _seed_run(db_session)
    assert client.delete(f"/api/v1/runs/{rid}/tags/hw").status_code == 401


def test_delete_tag_requires_csrf(client, db_session):
    _login(client, db_session)
    rid = _seed_run(db_session)
    assert client.delete(f"/api/v1/runs/{rid}/tags/hw").status_code == 403


def test_update_tag(client, db_session):
    _login(client, db_session)
    rid = _seed_run(db_session)
    csrf = client.cookies.get("prism_csrf")
    h = {"X-Prism-Csrf": csrf}
    client.post(f"/api/v1/runs/{rid}/tags", json={"key": "hw", "value": "a"}, headers=h)
    r = client.put(f"/api/v1/runs/{rid}/tags/hw", json={"value": "b"}, headers=h)
    assert r.status_code == 200
    assert r.json() == {"key": "hw", "value": "b"}
    assert RunRepo(db_session).get_tag(rid, "hw").value == "b"
    events = [
        e.action
        for e in AuditRepo(db_session).list_for_project(db_session.get(TestRun, rid).project_id)
    ]
    assert "run.tag.update" in events
    ev = _latest_event(db_session, db_session.get(TestRun, rid).project_id, "run.tag.update")
    assert ev.detail == {"key": "hw", "old_value": "a", "new_value": "b"}


def test_update_missing_tag_404(client, db_session):
    _login(client, db_session)
    rid = _seed_run(db_session)
    csrf = client.cookies.get("prism_csrf")
    r = client.put(
        f"/api/v1/runs/{rid}/tags/hw",
        json={"value": "b"},
        headers={"X-Prism-Csrf": csrf},
    )
    assert r.status_code == 404


def test_delete_tag(client, db_session):
    _login(client, db_session)
    rid = _seed_run(db_session)
    csrf = client.cookies.get("prism_csrf")
    h = {"X-Prism-Csrf": csrf}
    client.post(f"/api/v1/runs/{rid}/tags", json={"key": "hw", "value": "a"}, headers=h)
    r = client.delete(f"/api/v1/runs/{rid}/tags/hw", headers=h)
    assert r.status_code == 204
    assert RunRepo(db_session).get_tag(rid, "hw") is None
    events = [
        e.action
        for e in AuditRepo(db_session).list_for_project(db_session.get(TestRun, rid).project_id)
    ]
    assert "run.tag.delete" in events
    ev = _latest_event(db_session, db_session.get(TestRun, rid).project_id, "run.tag.delete")
    assert ev.detail == {"key": "hw", "value": "a"}


def test_delete_missing_tag_404(client, db_session):
    _login(client, db_session)
    rid = _seed_run(db_session)
    csrf = client.cookies.get("prism_csrf")
    r = client.delete(f"/api/v1/runs/{rid}/tags/hw", headers={"X-Prism-Csrf": csrf})
    assert r.status_code == 404
