# Getting started

## Prerequisites

- Docker + Docker Compose
- A free port for each service: 8000 (api), 8180 (web), 5433 (postgres), 6380 (redis), 9100/9101 (minio). Override any in `deploy/.env`.

## First run

1. `cp deploy/.env.example deploy/.env`
2. Edit `deploy/.env`: set `JWT_SECRET` to a random ≥32-character string, change `ADMIN_PASSWORD`.
3. `make up`
4. Visit http://localhost:8180 — log in with the admin email/password from `.env`.

## Upload a run via curl

```bash
# Login (saves cookies including the CSRF token)
curl -s -c /tmp/p.txt -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"...your password..."}' \
  http://localhost:8000/api/v1/auth/login

# Read CSRF token out of the cookie jar
CSRF=$(awk -F'\t' '/prism_csrf/{print $7}' /tmp/p.txt)

# Create a project
curl -s -b /tmp/p.txt -H 'Content-Type: application/json' \
  -H "X-Prism-Csrf: $CSRF" \
  -d '{"slug":"my-project","name":"My Project"}' \
  http://localhost:8000/api/v1/projects

# Upload a run (junit.xml + optional zip of waveforms)
curl -s -b /tmp/p.txt -H "X-Prism-Csrf: $CSRF" \
  -F 'junit=@./junit.xml;type=application/xml' \
  -F 'archive=@./artifacts.zip;type=application/zip' \
  -F 'metadata={"project_slug":"my-project","name":"build-42","tags":{"branch":"main"}}' \
  http://localhost:8000/api/v1/runs
```

## File naming convention for archive uploads

Files inside the archive follow `{suite}__{case}__{label}.{ext}`:

- `dsp__sine_sweep_1khz__waveform.csv` → attached to suite `dsp`, case `sine_sweep_1khz`
- `dsp__suite-log.log` → attached to suite `dsp`
- `readme.log` → attached to the run

Supported artifact types: `*.xml` (JUnit), `*.csv` `*.npy` `*.h5` (waveforms), `*.wav`, `*.png`, `*.log`. Anything else is stored as `other_binary`.

## Waveform CSV format

Single column of floats, optionally with a `# sample_rate=<int>` comment on the first line:

```
# sample_rate=48000
0.000000
0.130526
0.258819
...
```
