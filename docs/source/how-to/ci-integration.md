# Push results from CI

Prism accepts **one JUnit XML per Test Suite Run**. The recommended way to push
pytest results from CI is the committed helper at `scripts/upload_run.py` —
it's stdlib-only Python 3 (no `pip install` step) and handles auth, CSRF,
multipart upload, and optional wait-for-ingest in one command.

For the full flag and exit-code tables, see {doc}`../reference/upload-run-cli`.

## Use `scripts/upload_run.py`

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

Every `--flag` also reads its matching environment variable, so a hardened
pipeline can hide the credentials entirely:

```bash
export PRISM_URL=https://prism.internal
export PRISM_EMAIL=ci@example.com
export PRISM_PASSWORD=***
export PRISM_PROJECT=my-service
export PRISM_RUN_NAME="$CI_JOB_ID"

python3 scripts/upload_run.py results.xml \
  --tag branch="$GIT_BRANCH" --tag sha="$GIT_SHA" --wait
```

The final stdout line is always
`uploaded <run-name> (id=<uuid>, status=<status>)`, so CI can grep it for the
run ID.

## GitHub Actions

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

:::{tip}
Use `if: always()` so a failing test suite is still uploaded — a failed run is
exactly the one you want to inspect in Prism.
:::

## Bundling artifacts

To attach waveforms, logs and other measurement files, zip them and pass
`--archive`. Files inside the archive are routed to the right run/suite/case by
the `{suite}__{case}__{label}.{ext}` naming convention — see
{doc}`../reference/file-conventions`.

```bash
zip -r artifacts.zip waveforms/ logs/
python3 scripts/upload_run.py results.xml --archive artifacts.zip --wait
```

:::{note}
A long-lived Prism user account for CI is the simplest pattern today. Dedicated
API tokens are planned for a future release.
:::
