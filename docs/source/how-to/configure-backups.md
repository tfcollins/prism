# Back up the databases to Cloudsmith

Prism ships an optional **backup** container that, on a schedule, dumps the
Postgres metadata database and (optionally) the MinIO artifact bucket, pushes
each as a **raw package** to [Cloudsmith](https://cloudsmith.io/), and prunes
older backups so only the most recent `BACKUP_KEEP` of each are kept
(rotational backups).

It's **off by default** — you opt in with a compose profile plus a Cloudsmith
API key and repository.

## Enable it

In `deploy/.env` (uncomment the block from `.env.example`):

```bash
COMPOSE_PROFILES=backup
CLOUDSMITH_API_KEY=your-cloudsmith-api-key
CLOUDSMITH_REPO=my-org/my-repo        # owner/repository
BACKUP_CRON=0 3 * * *                 # daily at 03:00 UTC (standard cron)
BACKUP_KEEP=7                         # retain the 7 most recent of each
BACKUP_INCLUDE_MINIO=true             # also archive the MinIO bucket
```

Then bring the stack up as usual (`make up`, or `make deploy` in production).
The `backup` service starts only when the `backup` profile is active.

| Setting | Default | Notes |
|---|---|---|
| `COMPOSE_PROFILES` | — | Must include `backup` for the container to start |
| `CLOUDSMITH_API_KEY` | — | Cloudsmith API key (required to upload) |
| `CLOUDSMITH_REPO` | — | `owner/repo` of the target Cloudsmith repository |
| `BACKUP_CRON` | `0 3 * * *` | Standard cron expression (UTC) |
| `BACKUP_KEEP` | `7` | How many of each backup to retain; older ones are pruned |
| `BACKUP_INCLUDE_MINIO` | `true` | Archive the MinIO bucket too (can be large) |
| `BACKUP_S3_BUCKET` | `prism` | Bucket to archive |

## What gets produced

Each run uploads raw packages versioned with a UTC timestamp
(`YYYYMMDDThhmmssZ`):

- **`prism-postgres`** — `pg_dump` of the metadata DB, gzipped
  (`prism-postgres-<ts>.sql.gz`).
- **`prism-minio`** — a `tar.gz` of the artifact bucket
  (`prism-minio-<ts>.tar.gz`), when `BACKUP_INCLUDE_MINIO=true`.

After each upload the container lists that package's versions newest-first and
deletes everything beyond `BACKUP_KEEP`.

## Run one now

To back up immediately instead of waiting for the schedule:

```bash
make backup
```

With no `CLOUDSMITH_API_KEY` set this performs the dumps and **skips** the
upload — a handy dry run to confirm Postgres/MinIO connectivity.

## Restore

```bash
# Postgres
gunzip -c prism-postgres-<ts>.sql.gz | \
  docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"

# MinIO bucket
tar -xzf prism-minio-<ts>.tar.gz -C ./restore
mc mirror ./restore/prism bk/prism      # bk = your `mc alias set` for MinIO
```

:::{note}
The MinIO archive grows with your artifact volume. If it gets large, set
`BACKUP_INCLUDE_MINIO=false` and rely on MinIO's own replication/bucket
versioning for blob durability, keeping Cloudsmith for the (small) Postgres
dump that holds all the metadata.
:::

:::{important}
The Postgres dump contains user records (password hashes for local accounts).
Treat the Cloudsmith repository as sensitive and keep it private.
:::
