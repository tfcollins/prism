"""Combined test-results PDF for several runs.

Unlike the comparison report (per-run columns + deltas), this lays the selected
runs' results out as flat tables with a Run column — a consolidated report of
the test cases and measurements across the runs, not a comparison. Pure-Python
(fpdf2) like the other reports. Works for a single run too.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fpdf import FPDF


@dataclass
class CombinedRunSummary:
    run_name: str
    status: str
    pass_count: int
    fail_count: int


@dataclass
class CombinedCaseRow:
    run_name: str
    suite: str
    case: str
    status: str


@dataclass
class CombinedMeasurementRow:
    run_name: str
    name: str
    value: float
    unit: str | None
    spec_min: float | None
    spec_max: float | None
    margin: float | None
    in_spec: bool | None


def _safe(text: str) -> str:
    """fpdf2's core fonts are latin-1 only; replace anything outside it."""
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _fmt(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.4g}"


def _row(pdf: FPDF, cells: list[tuple[str, float]], *, height: float = 6) -> None:
    for text, w in cells:
        pdf.cell(w, height, _safe(text), border=1)
    pdf.ln(height)


def build_combined_report_pdf(
    *,
    project_names: list[str],
    summaries: list[CombinedRunSummary],
    case_rows: list[CombinedCaseRow],
    measurement_rows: list[CombinedMeasurementRow],
    generated_at: datetime,
) -> bytes:
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # --- header ---------------------------------------------------------------
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Combined test report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    if len(project_names) <= 1:
        proj = project_names[0] if project_names else "-"
        pdf.cell(0, 6, _safe(f"Project: {proj}"), new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(
            0,
            6,
            _safe(f"Projects: {', '.join(project_names)}  (runs span multiple projects)"),
            new_x="LMARGIN",
            new_y="NEXT",
        )
    pdf.cell(0, 6, f"Runs: {len(summaries)}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(
        0,
        6,
        f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    # --- runs summary ---------------------------------------------------------
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Runs", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 9)
    _row(pdf, [("Run", 167), ("Status", 40), ("Pass", 35), ("Fail", 35)], height=7)
    pdf.set_font("Helvetica", "", 9)
    for s in summaries:
        _row(
            pdf,
            [
                (s.run_name[:90], 167),
                (s.status, 40),
                (str(s.pass_count), 35),
                (str(s.fail_count), 35),
            ],
        )

    # --- test cases -----------------------------------------------------------
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Test cases", new_x="LMARGIN", new_y="NEXT")
    case_cols = [("Run", 75.0), ("Suite", 55.0), ("Case", 107.0), ("Status", 40.0)]
    pdf.set_font("Helvetica", "B", 9)
    _row(pdf, case_cols, height=7)
    pdf.set_font("Helvetica", "", 9)
    if not case_rows:
        pdf.cell(0, 6, "No test cases.", new_x="LMARGIN", new_y="NEXT")
    for c in case_rows:
        _row(
            pdf,
            [(c.run_name[:42], 75.0), (c.suite[:30], 55.0), (c.case[:62], 107.0), (c.status, 40.0)],
        )

    # --- measurements ---------------------------------------------------------
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Measurements", new_x="LMARGIN", new_y="NEXT")
    meas_cols = [
        ("Run", 55.0),
        ("Measurement", 62.0),
        ("Value", 40.0),
        ("Min", 28.0),
        ("Max", 28.0),
        ("Margin", 28.0),
        ("Result", 36.0),
    ]
    pdf.set_font("Helvetica", "B", 9)
    _row(pdf, meas_cols, height=7)
    pdf.set_font("Helvetica", "", 9)
    if not measurement_rows:
        pdf.cell(0, 6, "No measurements recorded.", new_x="LMARGIN", new_y="NEXT")
    for m in measurement_rows:
        unit = f" {m.unit}" if m.unit else ""
        result = "-" if m.in_spec is None else ("PASS" if m.in_spec else "FAIL")
        _row(
            pdf,
            [
                (m.run_name[:30], 55.0),
                (m.name[:34], 62.0),
                (f"{_fmt(m.value)}{unit}", 40.0),
                (_fmt(m.spec_min), 28.0),
                (_fmt(m.spec_max), 28.0),
                (_fmt(m.margin), 28.0),
                (result, 36.0),
            ],
        )

    return bytes(pdf.output())
