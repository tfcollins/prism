from prism_api.reports.run_report import ReportMeasurement, RunReport, build_run_report_pdf


def _report(**overrides: object) -> RunReport:
    base: dict[str, object] = {
        "run_name": "build-1",
        "project_name": "RF",
        "status": "pass",
        "tags": {"dut": "A1"},
        "pass_count": 3,
        "fail_count": 1,
        "measurements": [
            ReportMeasurement(
                name="channel_power_dBm",
                value=-10.5,
                unit="dBm",
                spec_min=None,
                spec_max=-9.0,
                in_spec=True,
                margin=1.5,
            )
        ],
        "junit_sha": "abc123",
    }
    base.update(overrides)
    return RunReport(**base)  # type: ignore[arg-type]


def test_build_pdf_returns_pdf_bytes() -> None:
    out = build_run_report_pdf(_report())
    assert isinstance(out, bytes)
    assert out[:5] == b"%PDF-"


def test_build_pdf_handles_no_measurements() -> None:
    out = build_run_report_pdf(_report(measurements=[]))
    assert out[:5] == b"%PDF-"


def test_build_pdf_sanitizes_non_latin1_text() -> None:
    """Unicode in tags / names must not crash fpdf2's latin-1 core font."""
    out = build_run_report_pdf(
        _report(
            run_name="café-Δ-build",
            tags={"site": "Tōkyō"},
            measurements=[
                ReportMeasurement(
                    name="EVM_µ",
                    value=2.5,
                    unit="%",
                    spec_min=None,
                    spec_max=5.0,
                    in_spec=True,
                    margin=2.5,
                )
            ],
        )
    )
    assert out[:5] == b"%PDF-"
