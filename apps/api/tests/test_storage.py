"""Storage layer tests using moto (in-process S3)."""
from io import BytesIO

import boto3
import pytest
from moto import mock_aws

from prism_api.storage import ObjectStorage, hash_bytes


@pytest.fixture
def storage():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="prism")
        yield ObjectStorage(client=client, bucket="prism")


def test_hash_bytes_is_sha256_hex():
    assert hash_bytes(b"hello") == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_put_and_get_round_trip(storage: ObjectStorage):
    payload = b"some bytes"
    h = hash_bytes(payload)
    key = storage.put_raw(payload, filename="x.csv")
    assert key.startswith("raw/")
    assert h in key

    body, _size = storage.get(key)
    assert body.read() == payload


def test_put_raw_is_idempotent(storage: ObjectStorage):
    payload = b"abc"
    k1 = storage.put_raw(payload, filename="x.csv")
    k2 = storage.put_raw(payload, filename="y.csv")  # same bytes, different filename
    assert k1 == k2  # content-addressed -> same key


def test_ensure_bucket_is_idempotent(storage: ObjectStorage):
    # Bucket already exists; method must not raise
    storage.ensure_bucket()
    storage.ensure_bucket()
