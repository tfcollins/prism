# Upload over raw HTTP (curl)

If you can't run Python — shell-only CI, a custom image — the same upload is
reachable with `curl`. The one thing to get right is the **double-submit CSRF
cookie**: every state-changing request must echo the `prism_csrf` cookie back
as the `X-Prism-Csrf` header.

## Log in and capture the CSRF token

```bash
curl -s -c /tmp/p.txt -H 'Content-Type: application/json' \
  -d "{\"email\":\"$PRISM_EMAIL\",\"password\":\"$PRISM_PASSWORD\"}" \
  "$PRISM_URL/api/v1/auth/login"

# Read the CSRF token out of the cookie jar
CSRF=$(awk -F'\t' '/prism_csrf/{print $7}' /tmp/p.txt)
```

## Create a project (once)

```bash
curl -s -b /tmp/p.txt -H 'Content-Type: application/json' \
  -H "X-Prism-Csrf: $CSRF" \
  -d '{"slug":"my-project","name":"My Project"}' \
  "$PRISM_URL/api/v1/projects"
```

## Upload a run

```bash
# Optionally bundle measurement artifacts first:
zip -r artifacts.zip waveforms/ logs/

curl -fs -b /tmp/p.txt -H "X-Prism-Csrf: $CSRF" \
  -F "junit=@junit.xml;type=application/xml" \
  -F "archive=@artifacts.zip;type=application/zip" \
  -F "metadata={\"project_slug\":\"my-project\",\"name\":\"build-42\",\"tags\":{\"branch\":\"main\",\"sha\":\"$GIT_SHA\"}}" \
  "$PRISM_URL/api/v1/runs"
```

The `metadata` part is a JSON blob with `project_slug`, `name`, and an optional
`tags` map. The `archive` part is optional.

:::{note}
Ingest is asynchronous: the upload returns a run in `pending`, and a Celery
worker flips it to `pass`/`fail`/`mixed`/`error` once parsing finishes. Poll
`GET /api/v1/runs/{id}` to watch the status change — or just use
`upload_run.py --wait`, which does the polling for you
({doc}`../reference/upload-run-cli`).
:::
