#!/usr/bin/env bash
# Entrypoint for the backup sidecar.
#   BACKUP_RUN_ONCE=1  -> run a single backup and exit (used by `make backup`)
#   otherwise          -> install BACKUP_CRON and run cron in the foreground
set -euo pipefail

if [ "${BACKUP_RUN_ONCE:-0}" = "1" ]; then
    exec /usr/local/bin/backup.sh
fi

cron_expr="${BACKUP_CRON:-0 3 * * *}"

# cron runs jobs with a stripped environment, so snapshot the current env into a
# root-only file that the job sources. `sh -c export -p` emits POSIX
# `export VAR='val'` lines (correctly quoted, incl. passwords) for /bin/sh.
mkdir -p /etc/backup
sh -c 'export -p' >/etc/backup/cron.env
chmod 600 /etc/backup/cron.env

# Send job output to PID 1's stdout so it shows up in `docker logs`.
printf '%s root . /etc/backup/cron.env; /usr/local/bin/backup.sh >> /proc/1/fd/1 2>&1\n' \
    "$cron_expr" >/etc/cron.d/prism-backup
chmod 0644 /etc/cron.d/prism-backup

echo "[backup] scheduled '$cron_expr' (keep=${BACKUP_KEEP:-7} minio=${BACKUP_INCLUDE_MINIO:-true})"
exec cron -f
