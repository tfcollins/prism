"""MatrixRepo.compute aggregation."""

from datetime import UTC, datetime, timedelta

from prism_api.models.project import Project
from prism_api.models.run import RunStatus, RunTag, TestRun
from prism_api.models.suite import TestSuite
from prism_api.repos.matrix import MatrixRepo
from prism_api.repos.matrix_config import DEFAULT_MATRIX_CONFIG


def _run(session, project_id, *, name, status, finished_at, tags, counts=(1, 0)):
    run = TestRun(project_id=project_id, name=name, status=status, finished_at=finished_at)
    session.add(run)
    session.flush()
    for k, v in tags.items():
        session.add(RunTag(run_id=run.id, key=k, value=v))
    passed, failed = counts
    session.add(
        TestSuite(
            run_id=run.id,
            name="s",
            pass_count=passed,
            fail_count=failed,
            error_count=0,
            skip_count=0,
            duration_ms=0,
        )
    )
    session.flush()
    return run


def _project(session, slug="kuiper-linux"):
    p = Project(slug=slug, name=slug)
    session.add(p)
    session.flush()
    return p


def test_compute_picks_latest_run_per_cell(db_session):
    p = _project(db_session)
    now = datetime.now(UTC)
    _run(
        db_session,
        p.id,
        name="old",
        status=RunStatus.FAIL,
        finished_at=now - timedelta(hours=2),
        tags={"hw": "ad9081", "platform": "zcu102"},
        counts=(8, 4),
    )
    newer = _run(
        db_session,
        p.id,
        name="new",
        status=RunStatus.PASS,
        finished_at=now - timedelta(minutes=5),
        tags={"hw": "ad9081", "platform": "zcu102"},
        counts=(12, 0),
    )
    db_session.flush()

    res = MatrixRepo(db_session).compute(
        scope="project:kuiper-linux", boot_files=[], config=DEFAULT_MATRIX_CONFIG
    )
    cell = res["cells"]["ad9081|zcu102"]
    assert cell["run_id"] == newer.id
    assert cell["status"] == "pass"
    assert (cell["passed"], cell["total"]) == (12, 12)
    assert res["rows"] == ["ad9081"]
    assert res["cols"] == ["zcu102"]
    assert res["summary"]["pass"] == 1


def test_compute_marks_stale(db_session):
    p = _project(db_session)
    now = datetime.now(UTC)
    _run(
        db_session,
        p.id,
        name="r",
        status=RunStatus.PASS,
        finished_at=now - timedelta(hours=72),
        tags={"hw": "ad9081", "platform": "zcu102"},
    )
    db_session.flush()
    res = MatrixRepo(db_session).compute(
        scope="project:kuiper-linux",
        boot_files=[],
        config={**DEFAULT_MATRIX_CONFIG, "stale_after_hours": 48},
    )
    assert res["cells"]["ad9081|zcu102"]["stale"] is True


def test_compute_boot_file_filter(db_session):
    p = _project(db_session)
    now = datetime.now(UTC)
    _run(
        db_session,
        p.id,
        name="zmp",
        status=RunStatus.PASS,
        finished_at=now,
        tags={"hw": "ad9081", "platform": "zcu102", "boot_file": "zynqmp-common"},
    )
    _run(
        db_session,
        p.id,
        name="zq",
        status=RunStatus.FAIL,
        finished_at=now,
        tags={"hw": "ad9371", "platform": "zed", "boot_file": "zynq-common"},
    )
    db_session.flush()
    res = MatrixRepo(db_session).compute(
        scope="project:kuiper-linux", boot_files=["zynqmp-common"], config=DEFAULT_MATRIX_CONFIG
    )
    assert "ad9081|zcu102" in res["cells"]
    assert "ad9371|zed" not in res["cells"]
    assert sorted(res["boot_files"]) == ["zynq-common", "zynqmp-common"]


def test_compute_curated_extras_add_empty_rows_cols(db_session):
    p = _project(db_session)
    _run(
        db_session,
        p.id,
        name="r",
        status=RunStatus.PASS,
        finished_at=datetime.now(UTC),
        tags={"hw": "ad9081", "platform": "zcu102"},
    )
    db_session.flush()
    res = MatrixRepo(db_session).compute(
        scope="project:kuiper-linux",
        boot_files=[],
        config={**DEFAULT_MATRIX_CONFIG, "curated_rows": ["ad9152"], "curated_cols": ["vcu118"]},
    )
    assert res["rows"] == ["ad9081", "ad9152"]
    assert res["cols"] == ["vcu118", "zcu102"]
    # one real cell + (2 rows x 2 cols - 1) = 3 no-run intersections
    assert res["summary"]["no_run"] == 3


def test_compute_unplaced_runs_counted(db_session):
    p = _project(db_session)
    now = datetime.now(UTC)
    _run(
        db_session,
        p.id,
        name="ok",
        status=RunStatus.PASS,
        finished_at=now,
        tags={"hw": "ad9081", "platform": "zcu102"},
    )
    _run(
        db_session,
        p.id,
        name="nohw",
        status=RunStatus.PASS,
        finished_at=now,
        tags={"platform": "zcu102"},
    )
    db_session.flush()
    res = MatrixRepo(db_session).compute(
        scope="project:kuiper-linux", boot_files=[], config=DEFAULT_MATRIX_CONFIG
    )
    assert res["unplaced_runs"] == 1


def test_compute_excludes_pending_runs(db_session):
    p = _project(db_session)
    now = datetime.now(UTC)
    _run(
        db_session,
        p.id,
        name="pending",
        status=RunStatus.PENDING,
        finished_at=now,
        tags={"hw": "ad9081", "platform": "zcu102"},
    )
    db_session.flush()
    res = MatrixRepo(db_session).compute(
        scope="project:kuiper-linux", boot_files=[], config=DEFAULT_MATRIX_CONFIG
    )
    assert res["cells"] == {}
    assert res["rows"] == []


def test_compute_global_superset_by_release_tag(db_session):
    pa = _project(db_session, slug="proj-a")
    pb = _project(db_session, slug="proj-b")
    now = datetime.now(UTC)
    _run(
        db_session,
        pa.id,
        name="a",
        status=RunStatus.PASS,
        finished_at=now,
        tags={"hw": "ad9081", "platform": "zcu102", "kuiper-linux-release": "2024_R2"},
    )
    _run(
        db_session,
        pb.id,
        name="b",
        status=RunStatus.FAIL,
        finished_at=now,
        tags={"hw": "ad9371", "platform": "zed", "kuiper-linux-release": "2024_R2"},
    )
    _run(
        db_session,
        pb.id,
        name="untagged",
        status=RunStatus.PASS,
        finished_at=now,
        tags={"hw": "adrv9009", "platform": "zed"},
    )  # no release tag -> excluded
    db_session.flush()
    res = MatrixRepo(db_session).compute(
        scope="global", boot_files=[], config=DEFAULT_MATRIX_CONFIG
    )
    assert set(res["rows"]) == {"ad9081", "ad9371"}
    assert "adrv9009" not in res["rows"]
