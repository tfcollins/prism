# Export results (CSV & PDF)

Prism can export test results as a **CSV** spreadsheet or as **PDF reports**.
All exports are plain authenticated `GET` downloads, so the buttons are ordinary
download links — nothing is uploaded or changed.

## CSV export (whole project)

On a project dashboard, click **Export CSV** (top right). You get one row per
test case across every run in the project, left-joined to its measurements, so
cases without measurements still appear:

```text
run_name,run_status,created_at,suite,classname,case_name,case_status,
duration_ms,measurement,value,unit,spec_min,spec_max
```

Endpoint: `GET /api/v1/projects/{slug}/export.csv`.

## PDF reports

Select runs on the dashboard with the row checkboxes — an **Export PDF** action
appears (and **Compare** once two or more are selected):

```{image} ../_static/img/screenshots/export-actions.png
:alt: Selecting runs reveals Export PDF and Compare actions
:width: 100%
```

There are three PDF reports, each suited to a different question:

| Report | Where | Contents |
|---|---|---|
| **Per-run compliance** | Run detail → *Download compliance PDF*, or select **one** run → *Export PDF* | Run metadata + tags, a **table of every test case** (suite / case / status), the measurements table (value, limits, margin, pass/fail), and the source JUnit SHA-256. |
| **Combined test results** | Select **one or more** runs on the dashboard → *Export PDF* | A runs summary plus flat tables of **all test cases** and **all measurements** across the selected runs, each with a *Run* column. A consolidated report — not a comparison. |
| **Comparison** | Compare page → *Export PDF* | The Compare view as a PDF: per-run columns with a first→last pass-rate delta, a measurement matrix with deltas, and a per-case status matrix. |

Endpoints (all `GET`, authenticated, no CSRF — they download in place):

| Method & path | Report |
|---|---|
| `GET /api/v1/runs/{id}/report.pdf` | Per-run compliance |
| `GET /api/v1/runs/report.pdf?runs=a,b,…` | Combined test results |
| `GET /api/v1/compare/report.pdf?runs=a,b,…` | Comparison |

The `runs=` reports accept a comma-separated list of run ids (the dashboard fills
this in from your selection); they reject an empty list and cap the number of
runs, and return 404 if any id is unknown.
