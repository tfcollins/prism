#!/usr/bin/env bash
# Dump Postgres (always) and the MinIO bucket (optional), push each to Cloudsmith
# as a raw package, then prune to the most recent BACKUP_KEEP of each. A manifest
# describing the run is written to s3://<bucket>/_backups/<ts>.json so the admin
# panel can show backup history (written even on dry runs and failures).
#
# Env (all provided by the compose service):
#   POSTGRES_DB/USER/PASSWORD, PG_HOST
#   MINIO_ENDPOINT, MINIO_ROOT_USER/PASSWORD, BACKUP_S3_BUCKET, BACKUP_INCLUDE_MINIO
#   CLOUDSMITH_API_KEY, CLOUDSMITH_REPO  (owner/repo)
#   BACKUP_KEEP (default 7), BACKUP_DRY_RUN (1 = dump only, skip Cloudsmith)
set -euo pipefail

ts="$(date -u +%Y%m%dT%H%M%SZ)"
work="$(mktemp -d)"

pg_host="${PG_HOST:-postgres}"
db="${POSTGRES_DB:-prism}"
pg_user="${POSTGRES_USER:-prism}"
bucket="${BACKUP_S3_BUCKET:-prism}"
keep="${BACKUP_KEEP:-7}"
include_minio="${BACKUP_INCLUDE_MINIO:-true}"
dry="${BACKUP_DRY_RUN:-0}"

# Manifest fields — pessimistic defaults; flipped to success at the end.
status="error"
cloudsmith_status="skipped"
pg_bytes=""
minio_bytes=""

log() { echo "[backup] $*"; }

# mc alias for MinIO — used both to mirror the bucket and to store the manifest.
mc --quiet alias set bk "${MINIO_ENDPOINT:-http://minio:9000}" \
    "${MINIO_ROOT_USER:-}" "${MINIO_ROOT_PASSWORD:-}" >/dev/null 2>&1 || true

write_manifest() {
    local minc="false"
    [ "$include_minio" = "true" ] && minc="true"
    jq -n \
        --arg ts "$ts" --arg status "$status" --arg cs "$cloudsmith_status" \
        --argjson pg "${pg_bytes:-null}" --argjson mb "${minio_bytes:-null}" \
        --argjson minc "$minc" --argjson keep "${keep:-null}" \
        '{timestamp:$ts, status:$status, postgres_bytes:$pg, minio_included:$minc,
          minio_bytes:$mb, cloudsmith:$cs, keep:$keep, error:null}' \
        >"$work/manifest.json" 2>/dev/null || true
    mc --quiet cp "$work/manifest.json" "bk/$bucket/_backups/$ts.json" >/dev/null 2>&1 \
        || log "warn: could not write backup manifest"
}

cleanup() {
    write_manifest
    rm -rf "$work"
}
trap cleanup EXIT

log "$ts start (db=$db minio=$include_minio keep=$keep dry=$dry)"

# --- 1. Postgres -----------------------------------------------------------
pg_file="$work/prism-postgres-$ts.sql.gz"
PGPASSWORD="${POSTGRES_PASSWORD:-}" pg_dump -h "$pg_host" -U "$pg_user" -d "$db" \
    | gzip -9 >"$pg_file"
pg_bytes="$(stat -c %s "$pg_file")"
log "postgres dump $(du -h "$pg_file" | cut -f1)"

# --- 2. MinIO bucket -------------------------------------------------------
minio_file=""
if [ "$include_minio" = "true" ]; then
    mkdir -p "$work/minio"
    # mirror is a no-op-safe full copy of the bucket's current contents
    mc --quiet mirror --overwrite "bk/$bucket" "$work/minio/$bucket" >/dev/null 2>&1 || true
    minio_file="$work/prism-minio-$ts.tar.gz"
    tar -czf "$minio_file" -C "$work/minio" .
    minio_bytes="$(stat -c %s "$minio_file")"
    log "minio archive $(du -h "$minio_file" | cut -f1)"
fi

# --- 3. Push + rotate ------------------------------------------------------
push_raw() { # name file
    local name="$1" file="$2"
    log "uploading $name $ts ($(basename "$file"))"
    cloudsmith push raw "$CLOUDSMITH_REPO" "$file" \
        --name "$name" --version "$ts" \
        --api-key "$CLOUDSMITH_API_KEY" --no-wait-for-sync
}

rotate() { # name — keep the newest $keep versions, delete the rest
    local name="$1" slugs slug i=0
    slugs="$(cloudsmith list packages "$CLOUDSMITH_REPO" \
        --query "name:$name" --page-size 500 --output-format json \
        --api-key "$CLOUDSMITH_API_KEY" \
        | jq -r '(.data // .) | sort_by(.version) | reverse | .[].slug_perm')"
    for slug in $slugs; do
        i=$((i + 1))
        if [ "$i" -gt "$keep" ]; then
            log "pruning $name #$i ($slug)"
            cloudsmith delete "$CLOUDSMITH_REPO/$slug" --yes \
                --api-key "$CLOUDSMITH_API_KEY" || log "warn: failed to prune $slug"
        fi
    done
}

if [ "$dry" = "1" ] || [ -z "${CLOUDSMITH_API_KEY:-}" ] || [ -z "${CLOUDSMITH_REPO:-}" ]; then
    log "dry-run or Cloudsmith not configured; skipping upload/rotate"
    cloudsmith_status="skipped"
else
    push_raw "prism-postgres" "$pg_file"
    rotate "prism-postgres"
    if [ "$include_minio" = "true" ] && [ -n "$minio_file" ]; then
        push_raw "prism-minio" "$minio_file"
        rotate "prism-minio"
    fi
    cloudsmith_status="pushed"
fi

status="ok"
log "$ts done ($cloudsmith_status)"
