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
DEFAULT_PASSWORD = os.environ.get("PRISM_PASSWORD", "analog")
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


def _context_xml() -> str:
    """A small, realistic libiio context dump (emulated) for the context viewer.

    Recognised by the ingest detector (``<!DOCTYPE context …>``) as
    ``iio_context_xml`` and rendered as a device → channel → attribute tree.
    """
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<!DOCTYPE context [\n"
        "<!ELEMENT context (device | context-attribute)*>\n"
        "<!ELEMENT context-attribute EMPTY>\n"
        "<!ELEMENT device (channel | attribute | debug-attribute | buffer-attribute)*>\n"
        "<!ELEMENT channel (scan-element?, attribute*)>\n"
        "<!ELEMENT attribute EMPTY>\n"
        "<!ELEMENT scan-element EMPTY>\n"
        "]>\n"
        '<context name="xml" description="Emulated ad9361 context">\n'
        '  <context-attribute name="local,kernel" value="6.1.0" />\n'
        '  <context-attribute name="uri" value="ip:192.168.2.1" />\n'
        '  <device id="iio:device0" name="ad9361-phy">\n'
        '    <attribute name="calib_mode" value="auto" />\n'
        '    <attribute name="ensm_mode" value="fdd" />\n'
        '    <channel id="voltage0" type="output" name="TX_LO">\n'
        '      <attribute name="hardwaregain" value="-10.000000" />\n'
        '      <attribute name="sampling_frequency" value="30720000" />\n'
        "    </channel>\n"
        '    <channel id="altvoltage0" type="output" name="RX_LO">\n'
        '      <attribute name="frequency" value="2400000000" />\n'
        "    </channel>\n"
        "  </device>\n"
        '  <device id="iio:device1" name="cf-ad9361-lpc">\n'
        '    <channel id="voltage0" type="input">\n'
        '      <scan-element index="0" format="le:S12/16&gt;&gt;0" />\n'
        '      <attribute name="calibphase" value="0.000000" />\n'
        "    </channel>\n"
        "  </device>\n"
        "</context>\n"
    )


def _distorted_tone() -> Iterable[float]:
    """A 1 kHz fundamental with deliberate harmonics so the genalyzer markers
    show distortion: HD2 -40 dBc, HD3 -50 dBc, HD5 -55 dBc."""
    return _sum(
        _sine(1000, 1.0),
        _sine(2000, 0.01),
        _sine(3000, 0.003),
        _sine(5000, 0.0018),
    )


def _dsp_archive(
    sine_1k: Iterable[float],
    sine_5k: Iterable[float],
    impulse: Iterable[float],
    distorted: Iterable[float],
) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("dsp__sine_sweep_1khz__wave.csv", _csv(sine_1k))
        zf.writestr("dsp__sine_sweep_5khz__wave.csv", _csv(sine_5k))
        zf.writestr("dsp__harmonic_distortion__wave.csv", _csv(distorted))
        zf.writestr("dsp__impulse_response__wave.csv", _csv(impulse))
        # libiio context dump: run-scoped (run-level Context section) and
        # case-scoped on sine_sweep_1khz (shows in that test's case view).
        ctx = _context_xml()
        zf.writestr("context.xml", ctx)
        zf.writestr("dsp__sine_sweep_1khz__context.xml", ctx)
    return buf.getvalue()


def build_runs() -> list[RunSpec]:
    # Three dsp variants — each case has a waveform, with visible deltas.
    dsp_cases_ok = [
        ("codec", "sine_sweep_1khz", None),
        ("codec", "sine_sweep_5khz", None),
        ("codec", "harmonic_distortion", None),
        ("latency", "impulse_response", None),
    ]
    dsp_cases_one_fail = [
        ("codec", "sine_sweep_1khz", None),
        ("codec", "sine_sweep_5khz", "expected SNR >60dB, got 58.3dB"),
        ("codec", "harmonic_distortion", None),
        ("latency", "impulse_response", None),
    ]
    dsp_cases_two_fail = [
        ("codec", "sine_sweep_1khz", "noise floor regression"),
        ("codec", "sine_sweep_5khz", "harmonic distortion at 12kHz"),
        ("codec", "harmonic_distortion", None),
        ("latency", "impulse_response", None),
    ]

    # Baseline nightly-41: clean signals.
    arc_41 = _dsp_archive(
        sine_1k=_sine(1000),
        sine_5k=_sine(5000),
        impulse=_impulse(200),
        distorted=_distorted_tone(),
    )

    # Nightly-42: slightly drifted 1 kHz + added 12 kHz harmonic in the 5 kHz case
    # (triggers the documented failure on sine_sweep_5khz).
    arc_42 = _dsp_archive(
        sine_1k=_sine(1005),
        sine_5k=_sum(_sine(5000), _sine(12000, amp=0.3)),
        impulse=_impulse(180),
        distorted=_distorted_tone(),
    )

    # PR-17: regressions on both sine cases — noisier signals.
    arc_pr = _dsp_archive(
        sine_1k=_noisy(_sine(1000), amp=0.25),
        sine_5k=_noisy(_sine(5000), amp=0.40),
        impulse=_impulse(250),
        distorted=_distorted_tone(),
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


# Board names the boot-log parser will surface, keyed by platform.
_BOARD_BY_PLATFORM = {
    "zcu102": "Xilinx ZynqMP ZCU102",
    "zc706": "Xilinx Zynq ZC706",
    "zed": "Avnet ZedBoard",
    "a10soc": "Intel Arria10 SoC Dev Kit",
}
# Kernel commit shared across all runs of a release (and a distinct one for the
# release-less runs) so the boot summary's shared-kernel count has data.
_KERNEL_COMMIT_BY_RELEASE = {
    "2024_R2": "a1b2c3d4e5f6",
    None: "f6e5d4c3b2a1",
}
# HDL commit shared within a platform family so shared-hdl counts have data too.
_HDL_COMMIT_BY_PLATFORM = {
    "zcu102": "1111aaaa2222",
    "zc706": "3333bbbb4444",
    "zed": "3333bbbb4444",
    "a10soc": "5555cccc6666",
}


def _boot_log(
    board: str,
    kernel_commit: str,
    hdl_commit: str,
    *,
    errors: int = 0,
    warns: int = 0,
    probe_fail: bool = False,
    panic: bool = False,
) -> str:
    """Build a synthetic dmesg-style boot log the boot-log parser can read.

    The parser pulls the kernel version + commit from a ``Linux version …-g<sha>``
    line, the board from ``Machine model:``, and the HDL commit from a line
    matching ``(?i)hdl.*?<hex>``. The severity lines drive the error/warn/panic
    tallies; the "clean" lines deliberately avoid error/warn/fail keywords.
    """
    lines = [
        f"[    0.000000] Linux version 6.1.0-g{kernel_commit} (gcc 12.2.0) #1 SMP PREEMPT",
        f"[    0.000000] Machine model: {board}",
        "[    0.000000] Booting Linux on physical CPU 0x0",
        "[    1.234567] random: crng init done",
        f"[    2.345678] fpga_manager fpga0: writing system_top.bit, HDL {hdl_commit}",
        "[    3.456789] ad9081 spi1.0: device ready",
    ]
    for i in range(errors):
        lines.append(f"[    4.{i:06d}] ERROR: ad9081 calibration out of range (ch {i})")
    for i in range(warns):
        lines.append(f"[    5.{i:06d}] WARNING: clock domain {i} mismatch, retrying")
    if probe_fail:
        lines.append("[    6.000000] ad9081 spi1.0: probe failed with -ETIMEDOUT")
    if panic:
        lines.append("[    7.000000] Kernel panic - not syncing: VFS: Unable to mount root fs")
    lines.append("[    8.000000] Freeing unused kernel image memory: 2048K")
    return "\n".join(lines) + "\n"


def _boot_archive(boot_text: str) -> bytes:
    """Wrap a boot log as a run-scoped artifact (bare name → attaches to run)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("boot.log", boot_text)
    return buf.getvalue()


def build_kuiper_runs() -> list[RunSpec]:
    """Return RunSpec entries for the matrix dashboard seed data.

    Each tuple: (hw, platform, boot_file, expected_status, release_or_None)
    Status is driven by (pass_count, fail_count):
      pass  → (20, 0)
      fail  → (0, 20)   — all failures, no passes → FAIL
      mixed → (18, 2)

    Every run also carries a run-scoped ``boot.log`` so the boot summary, commit
    cross-referencing, and the runs-list boot-log badge all have demo data. Log
    severity tracks the run's status (clean for pass, errors + a probe failure
    for fail, warnings for mixed; one fail run additionally panics).
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

        board = _BOARD_BY_PLATFORM.get(platform, platform)
        kernel_commit = _KERNEL_COMMIT_BY_RELEASE.get(release, "0000deadbeef")
        hdl_commit = _HDL_COMMIT_BY_PLATFORM.get(platform, "9999feedface")
        if status == "fail":
            # The release-less zc706 fail panics; the other fail just errors out.
            boot = _boot_log(
                board, kernel_commit, hdl_commit, errors=2, probe_fail=True, panic=release is None
            )
        elif status == "mixed":
            boot = _boot_log(board, kernel_commit, hdl_commit, warns=2)
        else:
            boot = _boot_log(board, kernel_commit, hdl_commit)

        runs.append(
            RunSpec(
                name=run_name,
                suite=suite_name,
                tags=tags,
                junit_xml=_kuiper_junit(suite_name, pass_count, fail_count),
                archive_zip=_boot_archive(boot),
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
        help=(
            "Delete each seeded project entirely (cascading all its runs, artifacts, "
            "and blobs) before recreating it. Requires admin privileges."
        ),
    )
    args = p.parse_args(argv)

    client = PrismClient(args.url)
    print(f"→ logging in to {args.url} as {args.email} …", flush=True)
    client.login(args.email, args.password)

    if args.reset:
        print(f"  resetting project {args.project!r} (delete + recreate) …", flush=True)
        client.delete_project(args.project)
    client.ensure_project(args.project, DEFAULT_PROJECT_NAME)

    runs = build_runs()

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
    if args.reset:
        print(f"  resetting project {KUIPER_PROJECT_SLUG!r} (delete + recreate) …", flush=True)
        client.delete_project(KUIPER_PROJECT_SLUG)
    client.ensure_project(KUIPER_PROJECT_SLUG, KUIPER_PROJECT_NAME)

    kuiper_runs = build_kuiper_runs()

    for spec in kuiper_runs:
        tag_summary = ", ".join(f"{k}={v}" for k, v in spec.tags.items())
        boot = "+boot.log" if spec.archive_zip else ""
        print(f"  uploading {spec.name} ({tag_summary}) {boot}…", flush=True)
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
