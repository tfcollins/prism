"""API-token crypto helpers (kept dependency-free so deps.py can import them)."""

import hashlib
import secrets

TOKEN_PREFIX = "prism_"  # noqa: S105 - a non-secret display prefix, not a password


def generate_token() -> str:
    """A new opaque secret, e.g. ``prism_<43 url-safe chars>``."""
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def hash_token(raw: str) -> str:
    """SHA-256 hex of the secret — what we store and look up by."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def display_prefix(raw: str) -> str:
    """Short non-secret prefix shown in the UI (e.g. ``prism_AbCdEf``)."""
    return raw[:12]
