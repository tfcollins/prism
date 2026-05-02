"""L5: contract test against a real Prism instance.

Gated by PRISM_LIVE_URL. CI brings up Prism via `make up` from `prism/deploy/`
and exports the URL + admin creds before running this file.
"""

from __future__ import annotations

import os
import time

import pytest

from pytest_prism.client import PrismClient
from pytest_prism.config import Config
from pytest_prism.manifest import OutputDir
from pytest_prism.upload import upload

_URL = os.environ.get("PRISM_LIVE_URL")
_EMAIL = os.environ.get("PRISM_LIVE_EMAIL")
_PASSWORD = os.environ.get("PRISM_LIVE_PASSWORD")
_PROJECT = os.environ.get("PRISM_LIVE_PROJECT", "pytest-prism-contract")

pytestmark = pytest.mark.skipif(
    not (_URL and _EMAIL and _PASSWORD),
    reason="PRISM_LIVE_URL/EMAIL/PASSWORD must be set for L5 contract tests",
)


def _seed(out: OutputDir, suite: str, case: str) -> None:
    out.initialize()
    (out.root / "junit.xml").write_text(
        f'<testsuite name="{suite}"><testcase classname="cls" name="{case}"/></testsuite>'
    )
    out.write_case_artifact(
        case_nodeid=f"cls::{case}",
        filename="spectrum.html",
        content=b"<html><body>contract</body></html>",
        kind="adi.iq",
    )
    out.write_case_artifact(
        case_nodeid=f"cls::{case}",
        filename="metrics.json",
        content=b'{"sfdr_dbc": 60.5}',
        kind="adi.iq",
    )
    out.finalize(run_meta={"plugin_version": "0.1.0"})


def test_upload_run_appears_in_api(tmp_path):
    od = OutputDir(tmp_path / "out")
    _seed(od, suite="contract_suite", case=f"case_{int(time.time())}")

    client = PrismClient(_URL)
    client.login(_EMAIL, _PASSWORD)
    client.ensure_project(_PROJECT, name=_PROJECT, description="L5 contract")

    cfg = Config.from_argv(
        [
            "--prism-report",
            "--prism-url",
            _URL,
            "--prism-email",
            _EMAIL,
            "--prism-password",
            _PASSWORD,
            "--prism-project",
            _PROJECT,
            "--prism-run-name",
            f"contract-{int(time.time())}",
        ]
    )
    result = upload(od, cfg, poll_timeout_s=30.0, poll_interval_s=0.5)
    assert result.run_id

    # Verify via the GET endpoint.
    fetched = client.get_run(result.run_id)
    assert fetched["id"] == result.run_id
    # Attachments include the kind we set.
    attachments = fetched.get("attachments", [])
    kinds = {a.get("kind") for a in attachments}
    assert "adi.iq" in kinds, f"expected adi.iq in attachment kinds, got {kinds}"
