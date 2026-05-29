# Use the admin panel

Prism has an **Admin** panel for operators, reachable from the sidebar when you
are signed in as the admin account. It surfaces four things:

- **Accounts** — every user, their auth provider (local / ldap), and which one
  is the admin.
- **Backups** — recent backup runs (timestamp, status, Postgres/MinIO sizes,
  and whether they were pushed to Cloudsmith), read from the manifests the
  backup container writes. See {doc}`configure-backups`.
- **Activity** — a global feed of recent events: logins, account create/delete,
  run uploads, spec/mask edits.
- **Container logs** — the recent stdout of any stack service (api, worker, web,
  postgres, redis, minio).

## Who can access it

There is no role system. The **bootstrap admin** — the account whose email
matches `ADMIN_EMAIL` in `deploy/.env` — is the sole admin. For that account the
**Admin** item appears in the sidebar and `/api/v1/admin/*` returns data; for
everyone else those endpoints return `403` and the page redirects away. The
admin flag is computed from `ADMIN_EMAIL`, not stored, so changing the env var
changes who is admin (no migration).

## Container logs & the Docker socket

The container-log viewer reads the **Docker Engine API** over a socket mounted
**read-only** into the `api` service:

```yaml
# deploy/docker-compose.yml (api service)
volumes:
  - /var/run/docker.sock:/var/run/docker.sock:ro
```

:::{important}
Mounting the Docker socket — even read-only — gives the `api` container
host-level Docker visibility. The endpoint is admin-only, but if you don't want
that exposure, **remove the volume mount** (or unset `PRISM_DOCKER_SOCKET`): the
viewer then reports "container logs unavailable" and the rest of the admin panel
keeps working.
:::

If the socket isn't mounted, the Docker SDK is missing, or the named service
isn't running, the **Container logs** tab shows a clear "unavailable" message
rather than failing.

## Notes

- The **Activity** feed is backed by the `audit_events` table; logins and
  account changes are recorded there in addition to the existing project events.
- The **Backups** tab is populated by the backup container's manifests in object
  storage, so it shows runs even before any Cloudsmith upload (including dry
  runs). If you haven't enabled backups, the tab is simply empty.
