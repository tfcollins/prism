"""Run tag editing — repo methods + HTTP endpoints."""

from prism_api.models.project import Project
from prism_api.models.run import RunStatus, TestRun
from prism_api.repos.runs import RunRepo


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
