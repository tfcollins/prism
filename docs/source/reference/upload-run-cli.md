# `upload_run.py` reference

`scripts/upload_run.py` is the committed CI helper: stdlib-only Python 3 (no
`pip install` step) that handles auth, CSRF, multipart upload, and optional
wait-for-ingest. For task-oriented usage see {doc}`../how-to/ci-integration`.

## Flags

Every `--flag` also reads its matching environment variable.

| Flag | Env | Notes |
|---|---|---|
| `--url` | `PRISM_URL` | Default `http://localhost:8000` |
| `--email` | `PRISM_EMAIL` | Required |
| `--password` | `PRISM_PASSWORD` | Required |
| `--project` | `PRISM_PROJECT` | Required; must exist unless `--auto-create-project` |
| `--run-name` | `PRISM_RUN_NAME` | Required; the Test Suite Run name shown in the dashboard |
| `--tag key=value` | — | Repeatable. Becomes a tag chip on the run |
| `--archive PATH` | — | Optional zip of measurement artifacts (waveforms, logs) |
| `--measurement name=value[:unit[:min[:max]]]` | — | Repeatable. Inject a numeric measurement into a single-testcase JUnit |
| `--auto-create-project` | — | Create the project if missing |
| `--wait [SECONDS]` | — | Poll `GET /runs/:id` until no longer pending (default 60s) |
| `--quiet` / `--verbose` | — | Control stdout chatter |

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Upload succeeded (and, with `--wait`, the run reached a terminal status) |
| `2` | Missing required argument or input file |
| `3` | Authentication failed (bad email/password) |
| `4` | Project not found (pass `--auto-create-project` or create it first) |
| `5` | Upload rejected by the server |
| `6` | `--wait` timed out while the run was still `pending` |

The final line on stdout is always
`uploaded <run-name> (id=<uuid>, status=<status>)` so CI can grep it for the
run ID.
