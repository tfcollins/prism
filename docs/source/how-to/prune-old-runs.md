# Prune old runs (retention)

Over time a busy Prism instance accumulates runs you no longer need. The
`prism-api prune` command deletes runs older than a cutoff **and** garbage-collects
the artifact blobs they leave behind — while preserving blobs still referenced by
runs you keep (artifacts are content-addressed and shared across runs).

It's **off by default**: nothing is deleted unless you set a retention window.

## What it deletes

For every `TestRun` older than the cutoff, prune removes the run and everything
hanging off it — suites, cases, measurements, tags, boot-log reports and
findings, and the run's `Artifact` rows. It then deletes a MinIO blob **only**
when no surviving artifact (in any remaining run) still points at it, so shared
content is never orphaned out from under a run you kept.

## Run it manually

From the `api` container (or any environment with the package installed):

```bash
# Preview only — reports counts, deletes nothing
prism-api prune --days 90 --dry-run

# Actually delete runs older than 90 days
prism-api prune --days 90
```

`--days N` overrides the configured window for a single invocation. Without it,
prune uses `PRISM_RETENTION_DAYS`. If neither is set (or the value is `0`),
prune is disabled and exits without touching anything.

The command prints a one-line summary, e.g.:

```text
pruned: runs=12 artifacts=47 blobs=39 (older than 90d)
```

`blobs` counts the MinIO objects actually deleted (orphans only) — it is usually
lower than `artifacts` because shared content stays.

## Configure a default window

Set `PRISM_RETENTION_DAYS` in `deploy/.env`:

```bash
PRISM_RETENTION_DAYS=90   # 0 (default) disables retention
```

| Setting | Default | Notes |
|---|---|---|
| `PRISM_RETENTION_DAYS` | `0` | Runs older than this many days are eligible; `0` disables prune |

## Schedule it

Prune is a plain CLI command, so you can run it on whatever scheduler you
already use — a host `cron` entry, a Kubernetes `CronJob`, or alongside the
[backup sidecar](configure-backups.md). For example, a nightly host cron that
execs into the running container:

```bash
0 4 * * *  docker compose exec -T api prism-api prune --days 90
```

Always trial a new window with `--dry-run` first — deletes are permanent.
```{warning}
Pruning permanently deletes runs and their artifacts. Pair retention with the
[Cloudsmith backups](configure-backups.md) if you need a recovery path.
```
