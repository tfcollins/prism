# Getting started

This tutorial walks you from an empty checkout to a waveform plotted in the
browser. It takes about five minutes plus image-pull time. You'll need
**Docker** and **Docker Compose**.

## 1. Configure the stack

Prism ships as a docker-compose stack. Copy the example environment file and
set two required secrets:

```bash
git clone <repo> && cd prism
cp deploy/.env.example deploy/.env
```

Edit `deploy/.env`:

- **`JWT_SECRET`** — a random string of **at least 32 characters** (validated at
  startup; the stack refuses to boot otherwise).
- **`ADMIN_PASSWORD`** — the password for the bootstrap admin account
  (`ADMIN_EMAIL`, default `admin@example.com`).

:::{note}
Host ports default to non-standard values (`8180` web, `8000` api, `5433`
postgres, `6380` redis, `9100/9101` minio) to avoid colliding with anything
already running locally. Override any of them in `deploy/.env`.
:::

## 2. Bring it up

```bash
make up
```

This builds and starts seven services — `web`, `api`, `worker`, `postgres`,
`redis`, `minio`, and `docs`. The `up` target restarts the `web` container once
to defeat a bind-mount race in development (see the `Makefile` for the gory
details).

When it settles, open <http://localhost:8180> and log in with the admin
email/password you set in `deploy/.env`.

```{image} ../_static/img/screenshots/login.png
:alt: The Prism login screen with email and password fields
:class: prism-shot
:align: center
:width: 480px
```

## 3. Seed some data

So the UI has something realistic to render, run the demo seeder against the
running stack. It uploads six single-suite runs — three `dsp-*` runs that carry
waveform artifacts and three `api-*` runs with pass/fail metadata only:

```bash
PRISM_EMAIL=admin@example.com PRISM_PASSWORD='<your password>' \
  python3 scripts/seed_demo.py --reset
```

Refresh the **Projects** page and you'll see an `audio` project appear.

```{image} ../_static/img/screenshots/projects.png
:alt: The Projects list showing the seeded audio project
:class: prism-shot
:align: center
:width: 640px
```

## 4. Browse a project

Click into the `audio` project. The dashboard lists every Test Suite Run with
its status, pass/fail counts, suite name and tags, plus tabs for trends,
regressions, specs and commits across runs.

```{image} ../_static/img/screenshots/dashboard.png
:alt: The audio project dashboard with a runs table and tag filters
:class: prism-shot
:align: center
```

## 5. Open a run and see a waveform

Click a `dsp-*` run. The run-detail page shows the suite's test cases on the
left; selecting one with an attached waveform renders an interactive plot with
**Time domain** and **FFT** tabs. The right-hand panel surfaces the run's
status, tags, calibration link and a downloadable compliance PDF.

```{image} ../_static/img/screenshots/run-detail.png
:alt: A run-detail page showing a sine-sweep waveform in the time domain
:class: prism-shot
:align: center
```

Switch to the **FFT** tab to see the same artifact transformed to the frequency
domain — computed on the server with a Welch periodogram and cached:

```{image} ../_static/img/screenshots/fft.png
:alt: The FFT tab showing the frequency-domain view of the same waveform
:class: prism-shot
:align: center
```

## Next steps

You now have a working Prism. From here:

- Push results from your own pipeline → {doc}`../how-to/ci-integration`
- Emit numeric measurements from tests → {doc}`../how-to/record-measurements`
- Overlay signals across runs → {doc}`../how-to/compare-runs`
- Understand what happens on upload → {doc}`../explanation/ingest-pipeline`
