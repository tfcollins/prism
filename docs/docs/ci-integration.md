# Integrating with your CI

Prism accepts one JUnit XML per Test Suite Run. The recommended way to
push pytest results from CI is the committed helper at
`scripts/upload_run.py` — it's stdlib-only Python 3 (no `pip install`
step) and handles auth, CSRF, multipart upload, and optional
wait-for-ingest in one command.

## Recommended: `scripts/upload_run.py`

```bash
python3 scripts/upload_run.py results.xml \
  --url https://prism.internal \
  --email ci@example.com --password "$PRISM_PASSWORD" \
  --project my-service \
  --run-name "$CI_JOB_ID" \
  --tag branch="$GIT_BRANCH" \
  --tag sha="$GIT_SHA" \
  --archive artifacts.zip \
  --wait 60
```

Every `--flag` also reads its matching environment variable, so a
hardened pipeline can hide the credentials entirely:

```bash
# In CI config:
export PRISM_URL=https://prism.internal
export PRISM_EMAIL=ci@example.com
export PRISM_PASSWORD=***
export PRISM_PROJECT=my-service
export PRISM_RUN_NAME="$CI_JOB_ID"

python3 scripts/upload_run.py results.xml \
  --tag branch="$GIT_BRANCH" --tag sha="$GIT_SHA" --wait
```

### Flags

| Flag | Env | Notes |
|---|---|---|
| `--url` | `PRISM_URL` | Default `http://localhost:8000` |
| `--email` | `PRISM_EMAIL` | Required |
| `--password` | `PRISM_PASSWORD` | Required |
| `--project` | `PRISM_PROJECT` | Required; must exist unless `--auto-create-project` |
| `--run-name` | `PRISM_RUN_NAME` | Required; the Test Suite Run name shown in the dashboard |
| `--tag key=value` | — | Repeatable. Becomes a tag chip on the run |
| `--archive PATH` | — | Optional zip of measurement artifacts (waveforms, logs) |
| `--measurement name=value[:unit[:min[:max]]]` | — | Repeatable. Inject a numeric measurement into a single-testcase JUnit (e.g. `channel_power_dBm=-10.2:dBm::-9.0`) |
| `--auto-create-project` | — | Create the project if missing (skip the manual UI step) |
| `--wait [SECONDS]` | — | Poll `GET /runs/:id` until no longer pending (default 60s) |
| `--quiet` / `--verbose` | — | Control stdout chatter |

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Upload succeeded (and, with `--wait`, the run reached a terminal status) |
| `2` | Missing required argument or input file |
| `3` | Authentication failed (bad email/password) |
| `4` | Project not found (pass `--auto-create-project` or create it first) |
| `5` | Upload rejected by the server |
| `6` | `--wait` timed out while the run was still `pending` |

The final line on stdout is always `uploaded <run-name> (id=<uuid>, status=<status>)`
so CI can grep it for the run ID.

## GitHub Actions example

```yaml
- name: Upload to Prism
  if: always()   # still upload on test failures
  env:
    PRISM_URL: ${{ secrets.PRISM_URL }}
    PRISM_EMAIL: ${{ secrets.PRISM_EMAIL }}
    PRISM_PASSWORD: ${{ secrets.PRISM_PASSWORD }}
    PRISM_PROJECT: my-service
    PRISM_RUN_NAME: ${{ github.run_id }}
  run: |
    python3 scripts/upload_run.py \
      tests/results.xml \
      --tag branch=${{ github.ref_name }} \
      --tag sha=${{ github.sha }} \
      --wait 120
```

## Recording measurements from tests

If you run pytest, emit numeric measurements straight from the test body — they
flow into the JUnit `<properties>` and become first-class Prism measurements
with pass/fail margins, no extra upload step:

```python
from pytest_prism import record_measurement

def test_acpr():
    record_measurement("channel_power_dBm", -10.2, unit="dBm", spec_max=-9.0)
    record_measurement("acpr_dBc", -45.3, unit="dBc", spec_max=-40.0)
```

Plain pytest works too — `record_property("channel_power_dBm", -10.2)` plus the
optional `channel_power_dBm__unit` / `__min` / `__max` siblings. For non-pytest
CI, `upload_run.py --measurement` injects the same properties into a
single-testcase JUnit.

## Raw HTTP fallback

If you can't run Python (shell-only CI, custom image), the same upload
is reachable with `curl`. Note the double-submit CSRF cookie — you
must echo `prism_csrf` back as the `X-Prism-Csrf` header on the POST:

```bash
# After your test suite produces junit.xml, optionally bundle artifacts:
zip -r artifacts.zip waveforms/ logs/

curl -s -c /tmp/p.txt -H 'Content-Type: application/json' \
  -d "{\"email\":\"$PRISM_EMAIL\",\"password\":\"$PRISM_PASSWORD\"}" \
  "$PRISM_URL/api/v1/auth/login"

CSRF=$(awk -F'\t' '/prism_csrf/{print $7}' /tmp/p.txt)

curl -fs -b /tmp/p.txt -H "X-Prism-Csrf: $CSRF" \
  -F "junit=@junit.xml;type=application/xml" \
  -F "archive=@artifacts.zip;type=application/zip" \
  -F "metadata={\"project_slug\":\"$PROJECT\",\"name\":\"$BUILD_ID\",\"tags\":{\"branch\":\"$GIT_BRANCH\",\"sha\":\"$GIT_SHA\"}}" \
  "$PRISM_URL/api/v1/runs"
```

!!! note
    A long-lived Prism user account for CI is the simplest pattern in v1.
    Dedicated API tokens are planned for a future release.
