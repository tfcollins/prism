"""Multi-run comparison PDF report.

Renders the same cross-run data the Compare page shows (run summary, pass-rate
delta, measurement matrix, per-case status matrix, boot/commit info) as a
landscape A4 PDF. Pure-Python (fpdf2) like ``run_report.py`` so it carries no
system-library dependencies and runs the same in CI as locally.
"""

from __future__ import annotations

from datetime import datetime

from fpdf import FPDF

from prism_api.schemas.compare import CompareResponse

# Usable width on landscape A4 (297mm) minus the 10mm side margins fpdf uses.
_USABLE_MM = 277.0

# Compact single-letter status codes used when many runs are selected.
_STATUS_LETTER = {"pass": "P", "fail": "F", "skip": "S", "error": "E"}


def _safe(text: str) -> str:
    """fpdf2's core fonts are latin-1 only; replace anything outside it so a
    stray unicode tag value or measurement name can't crash report generation."""
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _fmt(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.4g}"


def _row(pdf: FPDF, cells: list[tuple[str, float]], *, height: float = 6) -> None:
    for text, w in cells:
        pdf.cell(w, height, _safe(text), border=1)
    pdf.ln(height)


def build_compare_report_pdf(
    *,
    data: CompareResponse,
    project_names: list[str],
    generated_at: datetime,
) -> bytes:
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    n = len(data.runs)

    # --- header ---------------------------------------------------------------
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Comparison report", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 11)
    if len(project_names) <= 1:
        proj = project_names[0] if project_names else "-"
        pdf.cell(0, 6, _safe(f"Project: {proj}"), new_x="LMARGIN", new_y="NEXT")
    else:
        joined = ", ".join(project_names)
        pdf.cell(
            0,
            6,
            _safe(f"Projects: {joined}  (runs span multiple projects)"),
            new_x="LMARGIN",
            new_y="NEXT",
        )
    pdf.cell(0, 6, f"Runs: {n}", new_x="LMARGIN", new_y="NEXT")
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
    for r in data.runs:
        _row(
            pdf,
            [(r.name[:90], 167), (r.status, 40), (str(r.pass_count), 35), (str(r.fail_count), 35)],
        )
    delta = "n/a" if data.pass_rate_delta is None else f"{data.pass_rate_delta * 100:.1f}%"
    pdf.ln(1)
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 6, f"Pass-rate delta (first -> last): {delta}", new_x="LMARGIN", new_y="NEXT")

    # --- measurements matrix --------------------------------------------------
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Measurements", new_x="LMARGIN", new_y="NEXT")
    if not data.measurement_diffs:
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 6, "No measurements recorded.", new_x="LMARGIN", new_y="NEXT")
    else:
        label_w = 70.0
        col_w = max(14.0, (_USABLE_MM - label_w) / (n + 1))
        pdf.set_font("Helvetica", "B", 8)
        header = [("Measurement", label_w)]
        header += [(r.name[:10], col_w) for r in data.runs]
        header.append(("Delta", col_w))
        _row(pdf, header, height=7)
        pdf.set_font("Helvetica", "", 8)
        for d in data.measurement_diffs:
            label = f"{d.name} ({d.unit})" if d.unit else d.name
            cells = [(label[:40], label_w)]
            cells += [(_fmt(v), col_w) for v in d.values]
            cells.append((_fmt(d.delta), col_w))
            _row(pdf, cells)

    # --- per-case status matrix ----------------------------------------------
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Case status", new_x="LMARGIN", new_y="NEXT")
    if not data.cases:
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 6, "No cases.", new_x="LMARGIN", new_y="NEXT")
    else:
        dense = n > 8
        suite_w, case_w = (45.0, 45.0) if dense else (60.0, 70.0)
        status_w = max(8.0, (_USABLE_MM - suite_w - case_w) / n)
        body_size = 7 if dense else 8

        pdf.set_font("Helvetica", "B", body_size)
        header = [("Suite", suite_w), ("Case", case_w)]
        header += [
            (r.name[:10] if not dense else str(i + 1), status_w) for i, r in enumerate(data.runs)
        ]
        _row(pdf, header, height=6)
        pdf.set_font("Helvetica", "", body_size)
        for c in data.cases:
            cells = [(c.suite_name[:30], suite_w), (c.name[:36], case_w)]
            for s in c.statuses:
                if s is None:
                    cells.append(("-", status_w))
                elif dense:
                    cells.append((_STATUS_LETTER.get(s, s[:1].upper()), status_w))
                else:
                    cells.append((s, status_w))
            _row(pdf, cells, height=5.5)
        if dense:
            pdf.set_font("Helvetica", "I", 7)
            pdf.cell(
                0,
                5,
                "Columns are run indexes (see Runs table); P=pass F=fail S=skip E=error",
                new_x="LMARGIN",
                new_y="NEXT",
            )

    # --- boot / commit --------------------------------------------------------
    if any(b is not None for b in data.boots):
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Boot / commit", new_x="LMARGIN", new_y="NEXT")
        cols = [
            ("Run", 120.0),
            ("Kernel", 30.0),
            ("HDL", 30.0),
            ("Errors", 25.0),
            ("Warns", 25.0),
            ("Panic", 25.0),
        ]
        pdf.set_font("Helvetica", "B", 9)
        _row(pdf, cols, height=7)
        pdf.set_font("Helvetica", "", 9)
        for r, boot in zip(data.runs, data.boots, strict=False):
            if boot is None:
                _row(
                    pdf,
                    [
                        (r.name[:65], 120.0),
                        ("-", 30.0),
                        ("-", 30.0),
                        ("-", 25.0),
                        ("-", 25.0),
                        ("-", 25.0),
                    ],
                )
                continue
            _row(
                pdf,
                [
                    (r.name[:65], 120.0),
                    ((boot.kernel_commit or "-")[:8], 30.0),
                    ((boot.hdl_commit or "-")[:8], 30.0),
                    (str(boot.error_count), 25.0),
                    (str(boot.warn_count), 25.0),
                    ("PANIC" if boot.has_panic else "-", 25.0),
                ],
            )

    return bytes(pdf.output())
