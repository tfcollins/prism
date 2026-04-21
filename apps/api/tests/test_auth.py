"""Auth helpers."""
from datetime import timedelta

import pytest

from prism_api.auth import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password() -> None:
    h = hash_password("hunter2")
    assert h != "hunter2"
    assert verify_password("hunter2", h)
    assert not verify_password("wrong", h)


def test_create_and_decode_token() -> None:
    token = create_access_token(subject="user-id-123", secret="s", ttl=timedelta(minutes=10))
    claims = decode_access_token(token, secret="s")
    assert claims.subject == "user-id-123"


def test_decode_rejects_bad_signature() -> None:
    token = create_access_token(subject="u", secret="s1", ttl=timedelta(minutes=10))
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, secret="s2")


def test_decode_rejects_expired_token() -> None:
    token = create_access_token(subject="u", secret="s", ttl=timedelta(seconds=-1))
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, secret="s")
