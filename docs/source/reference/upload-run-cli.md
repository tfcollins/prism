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
| `--archive PATH` | `PRISM_ARCHIVE` | Optional zip of measurement artifacts (waveforms, logs) |
| `--pytest-log PATH` | `PRISM_PYTEST_LOG` | Complete terminal transcript, merged into the archive as `terminal.log` |
| `--ci-json JSON_OR_PATH` | `PRISM_CI_JSON` | Explicit CI metadata object or JSON file |
| `--hardware-json JSON_OR_PATH` | `PRISM_HARDWARE_JSON` | Reserved hardware metadata object or JSON file |
| `--job-url URL` | `PRISM_CI_JOB_URL` | Exact job link, taking precedence over automatic resolution |
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

GitHub Actions detection records repository, workflow, run ID, rerun attempt,
job name, and an attempt-specific run URL. Set `PRISM_CI_MATRIX` to the job's
matrix JSON. With `GITHUB_TOKEN` or `GH_TOKEN` available, the uploader queries
the current attempt's jobs and resolves a unique display-name or active-runner
match. `PRISM_CI_JOB_NAME` can supply the full job display name. The UI uses
the workflow-run URL when an exact job link is unavailable.

Hardware metadata accepts `place`, `board`, `carrier`, `exporters`, `tags`,
`metadata_status`, and `collection_errors`. Capture this data while the
reservation is active. Run details expose optional `ci` and `hardware` objects.
