# Backup sidecar: dumps Postgres + the MinIO bucket on a schedule and pushes
# each as a raw package to Cloudsmith, pruning to the most recent BACKUP_KEEP.
#
# Based on postgres:16 (Debian) so pg_dump matches the 16.x server major. Adds
# the MinIO client (mc), the Cloudsmith CLI, jq and cron.
FROM postgres:16-bookworm

# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl cron jq python3 python3-venv tzdata \
    && rm -rf /var/lib/apt/lists/*

# Cloudsmith CLI in an isolated venv (kept off the system Python).
# hadolint ignore=DL3013
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir cloudsmith-cli
ENV PATH="/opt/venv/bin:${PATH}"

# MinIO client (static Go binary; works on glibc).
RUN curl -fsSL https://dl.min.io/client/mc/release/linux-amd64/mc \
        -o /usr/local/bin/mc \
    && chmod +x /usr/local/bin/mc

COPY backup.sh /usr/local/bin/backup.sh
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/backup.sh /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
