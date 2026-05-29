# apps/api/tests/test_repos_logs.py
from prism_api.parsers.logs import ParsedFinding, ParsedLog
from prism_api.repos.logs import LogRepo


def _parsed(kernel: str, hdl: str) -> ParsedLog:
    return ParsedLog(
        kernel_version="6.1.0",
        board="ZCU102",
        kernel_commit=kernel,
        hdl_commit=hdl,
        error_count=1,
        warn_count=2,
        has_panic=False,
        findings=[ParsedFinding(severity="error", line_no=3, text="boom")],
    )


def test_create_and_query(db_session) -> None:
    repo = LogRepo(db_session)
    repo.create_report(run_id="r1", artifact_id="a1", source="boot.log", parsed=_parsed("kc", "hd"))
    repo.create_report(run_id="r2", artifact_id="a2", source="boot.log", parsed=_parsed("kc", "hX"))
    db_session.flush()

    reports = repo.list_by_run("r1")
    assert len(reports) == 1
    assert len(repo.findings_for(reports[0].id)) == 1

    assert repo.commit_counts("kernel") == [("kc", 2)]
    assert sorted(repo.commit_counts("hdl")) == [("hX", 1), ("hd", 1)]
    assert repo.run_ids_for_commit("kernel", "kc") == {"r1", "r2"}
    assert repo.shared_count("kernel", "kc", exclude_run_id="r1") == 1
