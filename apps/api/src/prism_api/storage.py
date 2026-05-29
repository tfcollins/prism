"""MinIO / S3 storage wrapper — thin abstraction over boto3."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import IO, TYPE_CHECKING

import boto3

from prism_api.config import Settings

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client
else:
    S3Client = object  # type: ignore[assignment,misc]


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class ObjectStorage:
    """Content-addressed object store wrapper."""

    client: S3Client
    bucket: str
    public_endpoint: str | None = None
    """If set, presigned URLs are rewritten so the host portion points
    here instead of the internal s3 endpoint. Lets browsers running
    outside the docker network reach MinIO via the host-mapped port."""

    def ensure_bucket(self) -> None:
        existing = {b["Name"] for b in self.client.list_buckets().get("Buckets", [])}
        if self.bucket in existing:
            return
        self.client.create_bucket(Bucket=self.bucket)

    def put_raw(self, data: bytes, *, filename: str) -> str:
        """Store bytes at content-addressed key; return the key."""
        h = hash_bytes(data)
        key = f"raw/{h[:2]}/{h}"
        # S3 put is idempotent for same content; skip existence probe to save a round-trip
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=data, Metadata={"filename": filename}
        )
        return key

    def put_at(
        self, key: str, data: bytes, *, content_type: str = "application/octet-stream"
    ) -> None:
        """Write bytes to an explicit key (used for derived artifacts)."""
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> tuple[IO[bytes], int]:
        """Return (body stream, size)."""
        resp = self.client.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"], int(resp.get("ContentLength", 0))

    def get_bytes(self, key: str) -> bytes:
        body, _ = self.get(key)
        return body.read()

    def list_prefix(self, prefix: str, *, limit: int = 1000) -> list[str]:
        """Return object keys under a prefix (used to enumerate backup manifests)."""
        resp = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix, MaxKeys=limit)
        return [obj["Key"] for obj in resp.get("Contents", [])]

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except self.client.exceptions.ClientError:
            return False

    def presigned_url(self, key: str, *, expires_in: int = 900) -> str:
        url: str = self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires_in
        )
        if self.public_endpoint:
            internal = self.client.meta.endpoint_url.rstrip("/")
            public = self.public_endpoint.rstrip("/")
            if url.startswith(internal):
                url = public + url[len(internal) :]
        return url


def build_storage(settings: Settings) -> ObjectStorage:
    """Create an ObjectStorage instance from application settings."""
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name="us-east-1",
    )
    return ObjectStorage(
        client=client,
        bucket=settings.s3_bucket,
        public_endpoint=settings.s3_public_endpoint,
    )
