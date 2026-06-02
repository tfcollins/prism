"""Per-run compliance PDF report.

Pure-Python (fpdf2) so it carries no system-library dependencies and runs the
same in CI as locally. Layout: a header with run/DUT metadata, a measurements
table with margins and pass/fail, and a footer tying the page back to its
source JUnit by SHA.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fpdf import FPDF


@dataclass
class ReportMeasurement:
    name: str
    value: float
    unit: str | None
    spec_min: float | None
    spec_max: float | None
    in_spec: bool | None
    margin: float | None


@dataclass
class ReportCase:
    suite: str
    classname: str
    name: str
    status: str


@dataclass
class RunReport:
    run_name: str
    project_name: str
    status: str
    tags: dict[str, str]
    pass_count: int
    fail_count: int
    measurements: list[ReportMeasurement]
    cases: list[ReportCase] = field(default_factory=list)
    junit_sha: str | None = None


def _safe(text: str) -> str:
    """fpdf2's core fonts are latin-1 only; replace anything outside it so a
    stray unicode tag value or measurement name can't crash report generation."""
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _fmt(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.4g}"


def build_run_report_pdf(report: RunReport) -> bytes:
    pdf = FPDF(unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Compliance report", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, _safe(f"Project: {report.project_name}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _safe(f"Run: {report.run_name}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Status: {report.status}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(
        0,
        6,
        f"Cases: {report.pass_count} pass, {report.fail_count} fail",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    if report.tags:
        tag_str = ", ".join(f"{k}={v}" for k, v in sorted(report.tags.items()))
        pdf.cell(0, 6, _safe(f"Tags: {tag_str}"), new_x="LMARGIN", new_y="NEXT")

    # --- test cases: every test run, with its status ---
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Test cases", new_x="LMARGIN", new_y="NEXT")
    case_cols = [("Suite", 50), ("Case", 110), ("Status", 30)]
    pdf.set_font("Helvetica", "B", 9)
    for label, w in case_cols:
        pdf.cell(w, 7, label, border=1)
    pdf.ln(7)
    pdf.set_font("Helvetica", "", 9)
    if not report.cases:
        pdf.cell(0, 7, "No test cases recorded for this run.", new_x="LMARGIN", new_y="NEXT")
    for c in report.cases:
        for text, w in (
            (_safe(c.suite[:28]), 50),
            (_safe(c.name[:64]), 110),
            (c.status, 30),
        ):
            pdf.cell(w, 6, text, border=1)
        pdf.ln(6)

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Measurements", new_x="LMARGIN", new_y="NEXT")

    # table header
    cols = [("Name", 55), ("Value", 28), ("Min", 24), ("Max", 24), ("Margin", 24), ("Result", 25)]
    pdf.set_font("Helvetica", "B", 9)
    for label, w in cols:
        pdf.cell(w, 7, label, border=1)
    pdf.ln(7)

    pdf.set_font("Helvetica", "", 9)
    if not report.measurements:
        pdf.cell(0, 7, "No measurements recorded for this run.", new_x="LMARGIN", new_y="NEXT")
    for m in report.measurements:
        unit = f" {m.unit}" if m.unit else ""
        result = "-" if m.in_spec is None else ("PASS" if m.in_spec else "FAIL")
        cells = [
            (_safe(m.name[:34]), 55),
            (_safe(f"{_fmt(m.value)}{unit}"), 28),
            (_fmt(m.spec_min), 24),
            (_fmt(m.spec_max), 24),
            (_fmt(m.margin), 24),
            (result, 25),
        ]
        for text, w in cells:
            pdf.cell(w, 6, text, border=1)
        pdf.ln(6)

    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 8)
    sha = report.junit_sha or "n/a"
    pdf.cell(0, 5, f"Source JUnit SHA-256: {sha}", new_x="LMARGIN", new_y="NEXT")

    out = pdf.output()
    return bytes(out)
