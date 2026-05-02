"""Shared test fixtures for pytest-prism."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

import pytest


@dataclass
class FakePrismRecord:
    """Captures what was POSTed during a test."""

    runs: list[dict[str, Any]] = field(default_factory=list)
    multipart_bodies: list[bytes] = field(default_factory=list)
    auth_headers_seen: list[str] = field(default_factory=list)
    next_status_code: int = 201
    next_status_value: str = "ready"


def _make_handler(record: FakePrismRecord):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_a, **_kw):
            return  # silence

        def _read_body(self) -> bytes:
            length = int(self.headers.get("Content-Length", "0"))
            return self.rfile.read(length) if length else b""

        def do_POST(self):
            path = urlparse(self.path).path
            if path == "/api/v1/auth/login":
                self.send_response(200)
                self.send_header("Set-Cookie", "prism_session=abc; Path=/")
                self.send_header("Set-Cookie", "prism_csrf=xyz; Path=/")
                self.end_headers()
                self.wfile.write(b'{"ok": true}')
                return
            if path == "/api/v1/runs":
                body = self._read_body()
                record.multipart_bodies.append(body)
                record.auth_headers_seen.append(self.headers.get("Cookie", ""))
                run_id = f"run-{len(record.runs) + 1}"
                resp = {"id": run_id, "status": record.next_status_value, "url": f"/runs/{run_id}"}
                record.runs.append(resp)
                self.send_response(record.next_status_code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(resp).encode("utf-8"))
                return
            self.send_response(404)
            self.end_headers()

        def do_GET(self):
            path = urlparse(self.path).path
            if path.startswith("/api/v1/runs/"):
                run_id = path.rsplit("/", 1)[-1]
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {
                            "id": run_id,
                            "status": record.next_status_value,
                            "url": f"/runs/{run_id}",
                        }
                    ).encode("utf-8")
                )
                return
            self.send_response(404)
            self.end_headers()

    return Handler


@pytest.fixture
def fake_prism():
    """Spin up a localhost HTTP server that pretends to be Prism."""
    record = FakePrismRecord()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(record))
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        yield (f"http://127.0.0.1:{port}", record)
    finally:
        server.shutdown()
        server.server_close()
