"""Shared test fixtures."""
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from prism_api.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c
