# Configure LDAP authentication

Prism can authenticate users against an LDAP / Active Directory server using
the **search + bind** pattern, while keeping a **local admin** account that
always works — even if the directory is unreachable or misconfigured. This is
your break-glass login.

## How it works

- A **local** account (the bootstrap `ADMIN_EMAIL` admin, and anyone created via
  the users API) always authenticates against its local bcrypt password.
- Any **other** email is authenticated against LDAP: Prism binds as a service
  account (or anonymously) to search for the user's entry, then re-binds as that
  entry with the supplied password to verify it.
- On the first successful LDAP login, a Prism account is **auto-provisioned**
  (`auth_provider=ldap`, no local password). No manual user management needed.

The login form, API, and session cookies are unchanged — LDAP is transparent to
clients.

## Enable it

Set these in `deploy/.env` (uncomment the block from `.env.example`) and
`make up`:

```bash
LDAP_ENABLED=true
LDAP_SERVER=ldap://dir.example.com:389        # or ldaps://dir.example.com:636
LDAP_USER_BASE_DN=ou=people,dc=example,dc=com
LDAP_USER_FILTER=(mail={email})               # or (uid={username})
LDAP_BIND_DN=cn=service,dc=example,dc=com     # optional; omit for anonymous search
LDAP_BIND_PASSWORD=change-me
LDAP_EMAIL_ATTRIBUTE=mail
LDAP_START_TLS=false
```

| Setting | Env var | Notes |
|---|---|---|
| Enable LDAP | `LDAP_ENABLED` | `false` by default; only local auth when off |
| Server URI | `LDAP_SERVER` | `ldap://host:389` or `ldaps://host:636` (**required** when enabled) |
| Search base | `LDAP_USER_BASE_DN` | subtree to search for users (**required** when enabled) |
| User filter | `LDAP_USER_FILTER` | template with `{email}` and/or `{username}` (local part) |
| Service bind DN | `LDAP_BIND_DN` | account used to search; omit for an anonymous search |
| Service password | `LDAP_BIND_PASSWORD` | password for the bind DN |
| Email attribute | `LDAP_EMAIL_ATTRIBUTE` | attribute read for the account's email (default `mail`) |
| StartTLS | `LDAP_START_TLS` | upgrade a plain `ldap://` connection to TLS |

The filter's `{email}` and `{username}` placeholders are escaped before the
search, so directory-special characters in a login can't alter the query.

:::{important}
LDAP simple binds send the password to the directory. In production use
`ldaps://` (LDAP over TLS) **or** set `LDAP_START_TLS=true` so credentials are
never sent in clear text.
:::

## The local-admin fallback

The bootstrap admin (`ADMIN_EMAIL` / `ADMIN_PASSWORD`) is a local account.
Because Prism authenticates a *known local account locally*, the admin can log
in even when `LDAP_ENABLED=true` and the directory is down — use it to recover
or reconfigure. If an email exists as both a local and an LDAP user, the local
account wins.

## Verify

```bash
make up
# Log in with a directory user → account is auto-created (auth_provider=ldap)
# Log in with ADMIN_EMAIL/ADMIN_PASSWORD → still works (local fallback)
```

A quick throwaway directory for testing:

```bash
docker run --rm -p 389:389 \
  -e LDAP_ORGANISATION=Example -e LDAP_DOMAIN=example.org \
  -e LDAP_ADMIN_PASSWORD=admin osixia/openldap:1.5.0
```
