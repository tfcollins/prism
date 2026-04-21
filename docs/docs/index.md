# Prism

Self-hostable web app for managing and visualizing test results — JUnit XML pass/fail metadata plus measurement artifacts (waveforms, FFTs, logs).

**Why Prism?** When your test suite produces *both* pass/fail outcomes and signal data — e.g. DSP pipelines, RF benches, audio codecs — most CI dashboards drop the signal data on the floor. Prism stores it, lets you browse it, and overlay it across runs.

## Quickstart

```bash
git clone <repo>
cd prism
cp deploy/.env.example deploy/.env
make up
open http://localhost:8180
```

Default login is in `deploy/.env`. See [Getting started](getting-started.md) for next steps.
