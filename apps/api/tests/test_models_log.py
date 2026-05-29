# apps/api/tests/test_models_log.py
from prism_api.models.log import LogFinding, LogReport


def test_log_models_persist(db_session) -> None:
    r = LogReport(
        run_id="run-1",
        artifact_id="art-1",
        source="boot.log",
        kernel_version="6.1.0-g1a2b3c4",
        board="ZCU102",
        kernel_commit="1a2b3c4",
        hdl_commit="deadbeef",
        error_count=2,
        warn_count=3,
        has_panic=True,
    )
    db_session.add(r)
    db_session.flush()
    db_session.add(LogFinding(log_report_id=r.id, severity="error", line_no=10, text="boom"))
    db_session.flush()
    assert r.id and r.kernel_commit == "1a2b3c4"
