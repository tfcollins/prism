#!/usr/bin/env python3
"""Seed the Prism demo dataset.

Uploads six single-suite Test Suite Runs to a running Prism stack so that
the UI has realistic data to render: three `dsp-*` runs with waveform
artifacts (good for the compare/overlay view) and three `api-*` runs with
pass/fail metadata only.

Also seeds a `kuiper-linux` project with matrix-dashboard demo data: runs
tagged with `hw`, `platform`, `boot_file`, and (where applicable)
`kuiper-linux-release` so the per-project matrix at `/projects/kuiper-linux/matrix`
and the global release superset are populated.

The canonical shape assumed by the app is one JUnit upload == one
<testsuite> == one Test Suite Run. This script produces exactly that.

Usage:
    python3 scripts/seed_demo.py
    python3 scripts/seed_demo.py --url http://localhost:8000 --reset
    PRISM_EMAIL=me PRISM_PASSWORD=xyz python3 scripts/seed_demo.py

Uses only the standard library so it runs anywhere Python 3.10+ is present.
"""

from __future__ import annotations

import argparse
import io
import math
import os
import sys
import zipfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from _prism_client import PrismClient

DEFAULT_URL = os.environ.get("PRISM_URL", "http://localhost:8000")
DEFAULT_EMAIL = os.environ.get("PRISM_EMAIL", "admin@example.com")
DEFAULT_PASSWORD = os.environ.get("PRISM_PASSWORD", "change-me-in-prod")
DEFAULT_PROJECT_SLUG = "audio"
DEFAULT_PROJECT_NAME = "Audio"

FS = 48_000
DURATION_S = 0.5
N = int(FS * DURATION_S)
TWO_PI = 2 * math.pi


# --------------------------------------------------------------------------- #
# Signal generators
# --------------------------------------------------------------------------- #


def _sine(freq: float, amp: float = 1.0) -> Iterable[float]:
    for i in range(N):
        yield amp * math.sin(TWO_PI * freq * i / FS)


def _sum(*series: Iterable[float]) -> Iterable[float]:
    # Zip any number of generators and sum them.
    iters = [iter(s) for s in series]
    for _ in range(N):
        yield sum(next(it) for it in iters)


def _impulse(decay_tau_samples: int = 200) -> Iterable[float]:
    for i in range(N):
        yield math.exp(-i / decay_tau_samples) if i < decay_tau_samples * 5 else 0.0


def _noisy(source: Iterable[float], amp: float) -> Iterable[float]:
    # Deterministic pseudo-random from a hash — no numpy dependency.
    import random as _r

    rng = _r.Random(0xC0DE)  # noqa: S311
    for v in source:
        yield v + (rng.random() - 0.5) * 2 * amp


def _csv(samples: Iterable[float]) -> str:
    return "\n".join([f"# sample_rate={FS:d}", *(f"{x:.6f}" for x in samples)])


# --------------------------------------------------------------------------- #
# Dataset — six single-suite Test Suite Runs
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RunSpec:
    name: str
    suite: str
    tags: dict[str, str]
    junit_xml: bytes
    archive_zip: bytes | None


def _dsp_junit(cases: Sequence[tuple[str, str, str | None]]) -> bytes:
    """`cases` entries: (classname, name, failure_message_or_None)."""
    tests = len(cases)
    fails = sum(1 for _, _, f in cases if f is not None)
    total_time = 0.12 * tests
    parts = [
        '<?xml version="1.0"?>',
        "<testsuites>",
        f'  <testsuite name="dsp" tests="{tests}" failures="{fails}" time="{total_time:.2f}">',
    ]
    for classname, name, failure in cases:
        if failure is None:
            parts.append(f'    <testcase classname="{classname}" name="{name}" time="0.12"/>')
        else:
            parts.append(
                f'    <testcase classname="{classname}" name="{name}" time="0.12">'
                f'<failure message="{failure}">AssertionError traceback ...</failure>'
                f"</testcase>"
            )
    parts.append("  </testsuite>")
    parts.append("</testsuites>")
    return "\n".join(parts).encode("utf-8")


def _api_junit(cases: Sequence[tuple[str, str, str | None]]) -> bytes:
    tests = len(cases)
    fails = sum(1 for _, _, f in cases if f is not None)
    total_time = 0.04 * tests
    parts = [
        '<?xml version="1.0"?>',
        "<testsuites>",
        f'  <testsuite name="api" tests="{tests}" failures="{fails}" time="{total_time:.2f}">',
    ]
    for classname, name, failure in cases:
        if failure is None:
            parts.append(f'    <testcase classname="{classname}" name="{name}" time="0.04"/>')
        else:
            parts.append(
                f'    <testcase classname="{classname}" name="{name}" time="0.04">'
                f'<failure message="{failure}">AssertionError traceback ...</failure>'
                f"</testcase>"
            )
    parts.append("  </testsuite>")
    parts.append("</testsuites>")
    return "\n".join(parts).encode("utf-8")


def _dsp_archive(
    sine_1k: Iterable[float], sine_5k: Iterable[float], impulse: Iterable[float]
) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("dsp__sine_sweep_1khz__wave.csv", _csv(sine_1k))
        zf.writestr("dsp__sine_sweep_5khz__wave.csv", _csv(sine_5k))
        zf.writestr("dsp__impulse_response__wave.csv", _csv(impulse))
    return buf.getvalue()


def build_runs() -> list[RunSpec]:
    # Three dsp variants — each case has a waveform, with visible deltas.
    dsp_cases_ok = [
        ("codec", "sine_sweep_1khz", None),
        ("codec", "sine_sweep_5khz", None),
        ("latency", "impulse_response", None),
    ]
    dsp_cases_one_fail = [
        ("codec", "sine_sweep_1khz", None),
        ("codec", "sine_sweep_5khz", "expected SNR >60dB, got 58.3dB"),
        ("latency", "impulse_response", None),
    ]
    dsp_cases_two_fail = [
        ("codec", "sine_sweep_1khz", "noise floor regression"),
        ("codec", "sine_sweep_5khz", "harmonic distortion at 12kHz"),
        ("latency", "impulse_response", None),
    ]

    # Baseline nightly-41: clean signals.
    arc_41 = _dsp_archive(
        sine_1k=_sine(1000),
        sine_5k=_sine(5000),
        impulse=_impulse(200),
    )

    # Nightly-42: slightly drifted 1 kHz + added 12 kHz harmonic in the 5 kHz case
    # (triggers the documented failure on sine_sweep_5khz).
    arc_42 = _dsp_archive(
        sine_1k=_sine(1005),
        sine_5k=_sum(_sine(5000), _sine(12000, amp=0.3)),
        impulse=_impulse(180),
    )

    # PR-17: regressions on both sine cases — noisier signals.
    arc_pr = _dsp_archive(
        sine_1k=_noisy(_sine(1000), amp=0.25),
        sine_5k=_noisy(_sine(5000), amp=0.40),
        impulse=_impulse(250),
    )

    # Three api variants — no waveforms attached, just pass/fail metadata.
    api_cases_ok = [
        ("upload", "happy_path", None),
        ("upload", "rejects_oversize", None),
        ("query", "lists_runs", None),
        ("query", "filters_by_tag", None),
    ]
    api_cases_one_fail = [
        ("upload", "happy_path", None),
        ("upload", "rejects_oversize", None),
        ("query", "lists_runs", "expected ordering newest-first"),
        ("query", "filters_by_tag", None),
    ]
    api_cases_new_endpoint = [
        ("upload", "happy_path", None),
        ("upload", "rejects_oversize", None),
        ("query", "lists_runs", None),
        ("query", "filters_by_tag", None),
        ("stream", "stream_endpoint", None),
    ]

    return [
        RunSpec(
            name="dsp-nightly-41",
            suite="dsp",
            tags={"branch": "main", "build": "nightly", "sha": "a1b2c3"},
            junit_xml=_dsp_junit(dsp_cases_ok),
            archive_zip=arc_41,
        ),
        RunSpec(
            name="dsp-nightly-42",
            suite="dsp",
            tags={"branch": "main", "build": "nightly", "sha": "d4e5f6"},
            junit_xml=_dsp_junit(dsp_cases_one_fail),
            archive_zip=arc_42,
        ),
        RunSpec(
            name="dsp-pr-17",
            suite="dsp",
            tags={"branch": "feature/dsp-rewrite", "build": "pr", "sha": "9a8b7c"},
            junit_xml=_dsp_junit(dsp_cases_two_fail),
            archive_zip=arc_pr,
        ),
        RunSpec(
            name="api-nightly-41",
            suite="api",
            tags={"branch": "main", "build": "nightly", "sha": "a1b2c3"},
            junit_xml=_api_junit(api_cases_ok),
            archive_zip=None,
        ),
        RunSpec(
            name="api-nightly-42",
            suite="api",
            tags={"branch": "main", "build": "nightly", "sha": "d4e5f6"},
            junit_xml=_api_junit(api_cases_one_fail),
            archive_zip=None,
        ),
        RunSpec(
            name="api-pr-17",
            suite="api",
            tags={"branch": "feature/streaming-api", "build": "pr", "sha": "9a8b7c"},
            junit_xml=_api_junit(api_cases_new_endpoint),
            archive_zip=None,
        ),
    ]


# --------------------------------------------------------------------------- #
# Matrix dashboard dataset — kuiper-linux project
# --------------------------------------------------------------------------- #

KUIPER_PROJECT_SLUG = "kuiper-linux"
KUIPER_PROJECT_NAME = "Kuiper Linux"


def _kuiper_junit(suite_name: str, pass_count: int, fail_count: int) -> bytes:
    """Build a minimal JUnit XML with the requested pass/fail distribution."""
    tests = pass_count + fail_count
    total_time = 0.08 * tests
    parts = [
        '<?xml version="1.0"?>',
        "<testsuites>",
        f'  <testsuite name="{suite_name}" tests="{tests}"'
        f' failures="{fail_count}" time="{total_time:.2f}">',
    ]
    for i in range(pass_count):
        parts.append(f'    <testcase classname="{suite_name}" name="test_{i:03d}" time="0.08"/>')
    for i in range(fail_count):
        parts.append(
            f'    <testcase classname="{suite_name}" name="test_fail_{i:03d}" time="0.08">'
            f'<failure message="test_fail_{i:03d} did not meet threshold">'
            f"AssertionError traceback ...</failure>"
            f"</testcase>"
        )
    parts.append("  </testsuite>")
    parts.append("</testsuites>")
    return "\n".join(parts).encode("utf-8")


def build_kuiper_runs() -> list[RunSpec]:
    """Return RunSpec entries for the matrix dashboard seed data.

    Each tuple: (hw, platform, boot_file, expected_status, release_or_None)
    Status is driven by (pass_count, fail_count):
      pass  → (20, 0)
      fail  → (0, 20)   — all failures, no passes → FAIL
      mixed → (18, 2)
    """
    matrix_entries: list[tuple[str, str, str, str, str | None]] = [
        ("ad9081", "zcu102", "zynqmp-common", "pass", "2024_R2"),
        ("ad9081", "zc706", "zynq-common", "fail", "2024_R2"),
        ("adrv9009", "zcu102", "zynqmp-common", "pass", "2024_R2"),
        ("adrv9009", "zed", "zynq-common", "mixed", "2024_R2"),
        ("ad9371", "zed", "zynq-common", "pass", None),
        ("ad9371", "zc706", "zynq-common", "fail", None),
        ("adrv9026", "a10soc", "socfpga_arria10_common", "pass", "2024_R2"),
    ]

    runs: list[RunSpec] = []
    for hw, platform, boot_file, status, release in matrix_entries:
        if status == "pass":
            pass_count, fail_count = 20, 0
        elif status == "fail":
            pass_count, fail_count = 0, 20
        else:  # mixed
            pass_count, fail_count = 18, 2

        suite_name = f"{hw}-{platform}"
        run_name = f"kuiper-{hw}-{platform}"

        tags: dict[str, str] = {
            "hw": hw,
            "platform": platform,
            "boot_file": boot_file,
        }
        if release is not None:
            tags["kuiper-linux-release"] = release

        runs.append(
            RunSpec(
                name=run_name,
                suite=suite_name,
                tags=tags,
                junit_xml=_kuiper_junit(suite_name, pass_count, fail_count),
                archive_zip=None,
            )
        )

    return runs


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    desc = __doc__.splitlines()[0] if __doc__ else "Seed Prism demo data"
    p = argparse.ArgumentParser(description=desc)
    p.add_argument("--url", default=DEFAULT_URL, help="Prism API base URL")
    p.add_argument("--email", default=DEFAULT_EMAIL, help="Login email")
    p.add_argument("--password", default=DEFAULT_PASSWORD, help="Login password")
    p.add_argument("--project", default=DEFAULT_PROJECT_SLUG, help="Project slug to seed")
    p.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing runs in the project whose names match the seed set before uploading",
    )
    args = p.parse_args(argv)

    client = PrismClient(args.url)
    print(f"→ logging in to {args.url} as {args.email} …", flush=True)
    client.login(args.email, args.password)
    client.ensure_project(args.project, DEFAULT_PROJECT_NAME)

    runs = build_runs()
    seed_names = {r.name for r in runs}

    if args.reset:
        existing = client.list_runs(args.project)
        for r in existing:
            if r["name"] in seed_names:
                print(f"  deleting existing run {r['name']} ({r['id']})", flush=True)
                client.delete_run(str(r["id"]))

    for spec in runs:
        has_waves = "yes" if spec.archive_zip else "no"
        print(
            f"  uploading {spec.name} (suite={spec.suite}, waveforms={has_waves}) …",
            flush=True,
        )
        client.upload_run(
            project_slug=args.project,
            run_name=spec.name,
            junit_xml=spec.junit_xml,
            archive_zip=spec.archive_zip,
            tags=spec.tags,
        )

    print(f"✓ seeded {len(runs)} runs into project {args.project!r}", flush=True)

    # ------------------------------------------------------------------ #
    # Kuiper-Linux matrix dashboard data
    # ------------------------------------------------------------------ #
    print(f"→ seeding matrix dashboard data into project {KUIPER_PROJECT_SLUG!r} …", flush=True)
    client.ensure_project(KUIPER_PROJECT_SLUG, KUIPER_PROJECT_NAME)

    kuiper_runs = build_kuiper_runs()
    kuiper_seed_names = {r.name for r in kuiper_runs}

    if args.reset:
        existing_kuiper = client.list_runs(KUIPER_PROJECT_SLUG)
        for r in existing_kuiper:
            if r["name"] in kuiper_seed_names:
                print(f"  deleting existing run {r['name']} ({r['id']})", flush=True)
                client.delete_run(str(r["id"]))

    for spec in kuiper_runs:
        tag_summary = ", ".join(f"{k}={v}" for k, v in spec.tags.items())
        print(f"  uploading {spec.name} ({tag_summary}) …", flush=True)
        client.upload_run(
            project_slug=KUIPER_PROJECT_SLUG,
            run_name=spec.name,
            junit_xml=spec.junit_xml,
            archive_zip=spec.archive_zip,
            tags=spec.tags,
        )

    print(f"✓ seeded {len(kuiper_runs)} runs into project {KUIPER_PROJECT_SLUG!r}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
