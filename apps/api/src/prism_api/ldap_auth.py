"""LDAP authentication (search + bind).

Flow: bind as a service account (or anonymously) to *search* for the user's
entry by a configurable filter, then re-bind as that entry's DN with the
user's password to *verify* the credential.

All network access goes through :func:`connect`, which tests monkeypatch with
an ``ldap3`` ``MOCK_SYNC`` connection so the search/bind logic is exercised
without a live directory.
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ldap3 import Connection, Server
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

if TYPE_CHECKING:
    from prism_api.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LdapIdentity:
    """A successfully authenticated directory user."""

    dn: str
    email: str


def connect(
    server_uri: str,
    user: str | None,
    password: str | None,
    *,
    settings: Settings,
) -> Connection:
    """Open a connection and attempt a simple bind. The only network seam.

    Returns the (possibly unbound) connection — callers check ``conn.bound``.
    """
    server = Server(server_uri, connect_timeout=settings.ldap_timeout)
    conn = Connection(
        server,
        user=user or None,
        password=password or None,
        auto_bind=False,
        receive_timeout=settings.ldap_timeout,
    )
    if settings.ldap_start_tls:
        conn.open()
        conn.start_tls()
    conn.bind()
    return conn


def _local_part(email: str) -> str:
    return email.split("@", 1)[0]


def _attr_value(entry: object, attr: str) -> str | None:
    try:
        value = entry[attr].value  # type: ignore[index]
    except (KeyError, LDAPException):
        return None
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value) if value is not None else None


def _safe_unbind(conn: Connection) -> None:
    with contextlib.suppress(LDAPException):  # best-effort cleanup
        conn.unbind()


def ldap_authenticate(email: str, password: str, settings: Settings) -> LdapIdentity | None:
    """Authenticate ``email``/``password`` against LDAP. Returns the identity or None.

    Returns None (not an exception) on any failure — wrong credentials, user not
    found, or directory errors — so the caller maps it to a 401.
    """
    # Guard: an empty password must never succeed. Many servers treat a bind
    # with an empty password as a successful *anonymous* bind, which would be an
    # authentication bypass.
    if not password:
        return None
    if not settings.ldap_server or not settings.ldap_user_base_dn:
        return None

    try:
        # 1. Search bind (service account or anonymous) to find the user's DN.
        search_conn = connect(
            settings.ldap_server,
            settings.ldap_bind_dn,
            settings.ldap_bind_password,
            settings=settings,
        )
        try:
            if not search_conn.bound:
                logger.warning("LDAP search bind failed (check PRISM_LDAP_BIND_DN/PASSWORD)")
                return None
            search_filter = settings.ldap_user_filter.format(
                email=escape_filter_chars(email),
                username=escape_filter_chars(_local_part(email)),
            )
            search_conn.search(
                settings.ldap_user_base_dn,
                search_filter,
                attributes=[settings.ldap_email_attribute],
            )
            entries = search_conn.entries
            if len(entries) != 1:
                return None
            entry = entries[0]
            user_dn = str(entry.entry_dn)
            resolved_email = _attr_value(entry, settings.ldap_email_attribute) or email
        finally:
            _safe_unbind(search_conn)

        # 2. Re-bind as the user to verify the password.
        user_conn = connect(settings.ldap_server, user_dn, password, settings=settings)
        try:
            if not user_conn.bound:
                return None
        finally:
            _safe_unbind(user_conn)
    except LDAPException as exc:
        logger.warning("LDAP authentication error: %s", exc)
        return None

    return LdapIdentity(dn=user_dn, email=resolved_email)
