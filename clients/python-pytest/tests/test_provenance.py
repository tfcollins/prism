"""CI metadata detection, exact-job resolution, and explicit producer metadata."""

import importlib.util
import json
from pathlib import Path

import pytest

from pytest_prism import client as plugin_client


def script_client():
    path = Path(__file__).resolve().parents[3] / "scripts" / "_prism_client.py"
    spec = importlib.util.spec_from_file_location("script_client", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=[plugin_client, script_client()])
def client_module(request):
    return request.param


def test_local_run_has_no_ci(client_module, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert client_module.detect_ci() is None


def test_matrix_rerun_metadata_and_explicit_job(client_module, monkeypatch):
    values = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "org/repo",
        "GITHUB_WORKFLOW": "Hardware",
        "GITHUB_RUN_ID": "52",
        "GITHUB_RUN_ATTEMPT": "3",
        "GITHUB_JOB": "hw",
        "PRISM_CI_MATRIX": '{"board":"adc","carrier":"zcu"}',
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    ci = client_module.detect_ci(job_url="https://github.com/org/repo/actions/runs/52/job/100")
    assert ci["run_id"] == "52"
    assert ci["attempt"] == "3"
    assert ci["matrix"] == {"board": "adc", "carrier": "zcu"}
    assert ci["run_url"].endswith("/52/attempts/3")
    assert ci["job_url"].endswith("/job/100")


def test_exact_job_only_resolved_when_unique(client_module):
    jobs = [
        {"name": "hw (adc, zcu)", "html_url": "https://github.com/job/1"},
        {"name": "hw (dac, zcu)", "html_url": "https://github.com/job/2"},
    ]
    assert (
        client_module.resolve_job_url(jobs, job_name="hw (adc, zcu)") == "https://github.com/job/1"
    )
    assert client_module.resolve_job_url(jobs, job_name="hw") is None
    assert client_module.resolve_job_url(jobs + jobs[:1], job_name="hw (adc, zcu)") is None


def test_client_upload_carries_explicit_provenance(client_module, fake_prism):
    url, record = fake_prism
    client_module.PrismClient(url).upload_run(
        project_slug="demo",
        run_name="test",
        junit_xml=b"<testsuites/>",
        ci={"provider": "other", "job_url": "https://ci.example/job"},
        hardware={"place": "reserved"},
    )
    body = record.multipart_bodies[0]
    payload = body.split(b'name="metadata"\r\n\r\n')[1].split(b"\r\n--")[0]
    meta = json.loads(payload)
    assert meta["ci"]["provider"] == "other"
    assert meta["hardware"]["place"] == "reserved"


def test_job_resolution_uses_unique_active_runner(client_module):
    jobs = [
        {
            "name": "caller / tests (adc)",
            "runner_name": "hardware-runner",
            "status": "in_progress",
            "html_url": "https://github.com/job/1",
        },
        {
            "name": "caller / tests (dac)",
            "runner_name": "hardware-runner",
            "status": "completed",
            "html_url": "https://github.com/job/2",
        },
    ]
    assert (
        client_module.resolve_job_url(jobs, job_name="tests", runner_name="hardware-runner")
        == "https://github.com/job/1"
    )
    assert (
        client_module.resolve_job_url(
            jobs + jobs[:1], job_name="tests", runner_name="hardware-runner"
        )
        is None
    )


def test_explicit_ci_environment_for_other_providers(client_module, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("PRISM_CI_JSON", '{"provider":"jenkins","run_url":"https://ci.example/5"}')
    assert client_module.detect_ci() == {"provider": "jenkins", "run_url": "https://ci.example/5"}


@pytest.mark.parametrize("api_available", [True, False])
def test_github_attempt_job_lookup_and_run_link_fallback(client_module, monkeypatch, api_available):
    import io
    import urllib.error

    for name in ["PRISM_CI_JSON", "PRISM_CI_JOB_URL", "GITHUB_JOB_URL"]:
        monkeypatch.delenv(name, raising=False)
    for name, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "org/repo",
        "GITHUB_RUN_ID": "52",
        "GITHUB_RUN_ATTEMPT": "3",
        "GITHUB_JOB": "hw",
        "PRISM_CI_JOB_NAME": "hw (adc, zcu)",
        "GITHUB_TOKEN": "fixture-token",
    }.items():
        monkeypatch.setenv(name, value)
    requests = []

    def fetch(request, *, timeout):
        requests.append(request)
        assert timeout == 5
        if not api_available:
            raise urllib.error.URLError("no Actions read access")
        return io.BytesIO(
            json.dumps(
                {"jobs": [{"name": "hw (adc, zcu)", "html_url": "https://github.com/job/42"}]}
            ).encode()
        )

    monkeypatch.setattr(client_module.urllib.request, "urlopen", fetch)
    ci = client_module.detect_ci()
    assert "/actions/runs/52/attempts/3/jobs?" in requests[0].full_url
    assert requests[0].get_header("Authorization") == "Bearer fixture-token"
    assert ci["run_url"].endswith("/52/attempts/3")
    if api_available:
        assert ci["job_url"] == "https://github.com/job/42"
    else:
        assert "job_url" not in ci
        assert ci["collection_errors"] == ["Exact GitHub job link unavailable"]
