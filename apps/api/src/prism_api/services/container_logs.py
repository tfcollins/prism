"""Read recent container logs via the Docker Engine API (admin panel).

Best-effort: if the Docker SDK isn't installed or the socket isn't mounted, this
returns an unavailable result with an explanation rather than raising — the rest
of the admin panel keeps working.
"""

from __future__ import annotations

import os

from prism_api.schemas.admin import ContainerLogsOut

# Only the stack's own services may be inspected.
ALLOWED_SERVICES = ("api", "worker", "web", "postgres", "redis", "minio", "backup")


def _unavailable(service: str, message: str) -> ContainerLogsOut:
    return ContainerLogsOut(service=service, available=False, message=message)


def read_container_logs(service: str, *, tail: int, socket_path: str) -> ContainerLogsOut:
    if service not in ALLOWED_SERVICES:
        return _unavailable(service, f"unknown service (allowed: {', '.join(ALLOWED_SERVICES)})")
    tail = max(1, min(tail, 2000))

    try:
        import docker  # imported lazily so the dep is optional
    except ImportError:
        return _unavailable(service, "docker SDK not installed")

    if not socket_path or not os.path.exists(socket_path):
        return _unavailable(service, "docker socket not mounted; container logs unavailable")

    try:
        client = docker.DockerClient(base_url=f"unix://{socket_path}")
        containers = client.containers.list(
            filters={"label": f"com.docker.compose.service={service}"}
        )
        if not containers:
            return _unavailable(service, f"no running container for service '{service}'")
        raw = containers[0].logs(tail=tail, timestamps=False)
        text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
        lines = [line for line in text.splitlines() if line]
        return ContainerLogsOut(service=service, available=True, lines=lines)
    except Exception as exc:  # surface any docker error as "unavailable"
        return _unavailable(service, f"error reading logs: {exc}")
